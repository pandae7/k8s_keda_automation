import click
from kubernetes import client
from k8s_automation.cluster import connect_to_cluster
from k8s_automation.tooling import (
    ensure_helm_installed,
    add_helm_repo,
    install_keda_chart,
    verify_keda_installation
)
from k8s_automation.deployment import validate_and_process_values, create_kubernetes_resources
from k8s_automation.health import get_deployment_status

@click.group()
@click.option('--context', help='The Kubernetes context to use. Overrides the current context in your kubeconfig.')
@click.pass_context
def cli(ctx, context):
    """A command-line tool to automate Kubernetes operations."""
    ctx.ensure_object(dict)
    ctx.obj['CONTEXT'] = context

@cli.command('check-connection')
@click.pass_context
def check_connection(ctx):
    """Checks the connection to the Kubernetes cluster."""
    k8s_context = ctx.obj.get('CONTEXT')
    click.echo(f"Attempting to connect to cluster (context: {k8s_context or 'default'})...")
    api_client = connect_to_cluster(context=k8s_context)
    
    if api_client:
        try:
            api_client.list_namespace(limit=1)
            click.echo(click.style("Successfully connected to the Kubernetes cluster.", fg='green'))
            if k8s_context:
                click.echo(f"Using context: '{k8s_context}'")
        except Exception as e:
            click.echo(click.style(f"Connection test failed. API error: {e}", fg='red'), err=True)
    else:
        click.echo(click.style("Failed to get a Kubernetes API client.", fg='red'), err=True)
        click.echo("Please check your kubeconfig file, context name, and network connection.", err=True)


@cli.command('install-tools')
@click.pass_context
def install_tools(ctx):
    """Installs KEDA on the cluster using Helm."""
    k8s_context = ctx.obj.get('CONTEXT')
    
    click.echo("Step 1: Ensuring Helm is installed...")
    if not ensure_helm_installed():
        return

    click.echo("\nStep 2: Connecting to Kubernetes cluster...")
    core_api = connect_to_cluster(context=k8s_context)
    if not core_api:
        return
    apps_api = client.AppsV1Api(core_api.api_client)
    click.echo(click.style("Successfully connected.", fg='green'))

    click.echo("\nStep 3: Adding KEDA Helm repository...")
    if not add_helm_repo():
        return
    click.echo(click.style("KEDA repo added successfully.", fg='green'))

    click.echo("\nStep 4: Installing KEDA chart (this may take a moment)...")
    if not install_keda_chart():
        return
    click.echo(click.style("KEDA chart installation command executed.", fg='green'))

    click.echo("\nStep 5: Verifying KEDA installation on the cluster...")
    if verify_keda_installation(apps_api):
        click.echo(click.style("\nKEDA installation successful and verified!", fg='cyan', bold=True))
    else:
        click.echo(click.style("\nKEDA installation failed or could not be verified.", fg='red', bold=True))


@cli.command('create-deployment')
@click.option('--values', 'values_path', type=click.Path(exists=True, dir_okay=False, readable=True), required=True, help='Path to a YAML file with deployment values.')
@click.pass_context
def create_deployment(ctx, values_path):
    """Creates a new deployment and KEDA ScaledObject from a YAML values file."""
    k8s_context = ctx.obj.get('CONTEXT')
    
    click.echo(f"-> Loading and validating values from '{values_path}'...")
    deployment_values = validate_and_process_values(values_path)
    if not deployment_values:
        return
    click.echo(click.style("Values file is valid.", fg='green'))

    click.echo(f"-> Connecting to Kubernetes cluster (context: {k8s_context or 'default'})...")
    core_api = connect_to_cluster(context=k8s_context)
    if not core_api:
        return
    
    click.echo(click.style("Successfully connected.", fg='green'))
    
    success, details = create_kubernetes_resources(core_api.api_client, deployment_values)

    if success:
        click.echo(click.style("\nDeployment Summary", fg='green', bold=True))
        click.echo("--------------------------")
        click.echo(f"  Deployment Name: {details['name']}")
        click.echo(f"  Namespace:       {details['namespace']}")
        click.echo(f"  Container Image: {details['image']}")
        click.echo(f"  Container Port:  {details['port']}")
        if 'scaling' in details:
            click.echo("\n  --- KEDA Scaling ---")
            click.echo(f"  Trigger Type:    {details['scaling']['trigger_type']}")
            click.echo(f"  Min/Max Replicas: {details['scaling'].get('min_replicas', 1)} / {details['scaling'].get('max_replicas', 10)}")
            click.echo(f"  ScaledObject:    {details['name']}-so")
        click.echo("--------------------------")
        click.echo(f"\nTo check status, run: python main.py get-status {details['name']} --namespace {details['namespace']}")


@cli.command('get-status')
@click.argument('deployment_name')
@click.option('--namespace', default='default', show_default=True, help='The namespace of the deployment.')
@click.pass_context
def get_status(ctx, deployment_name, namespace):
    """Gets the health status for a given deployment."""
    k8s_context = ctx.obj.get('CONTEXT')
    
    click.echo(f"-> Connecting to Kubernetes cluster (context: {k8s_context or 'default'})...")
    core_api = connect_to_cluster(context=k8s_context)
    if not core_api:
        return
    
    apps_api = client.AppsV1Api(core_api.api_client)
    click.echo(click.style("Successfully connected.", fg='green'))
    
    get_deployment_status(apps_api, core_api, deployment_name, namespace)


if __name__ == '__main__':
    cli()