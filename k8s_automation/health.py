# k8s_automation/health.py
from kubernetes import client
import click

def get_deployment_status(apps_api: client.AppsV1Api, core_api: client.CoreV1Api, name: str, namespace: str):
    """Fetches and displays the status of a deployment and its pods."""
    try:
        # 1. Get Deployment Status
        deployment = apps_api.read_namespaced_deployment_status(name=name, namespace=namespace)
        status = deployment.status
        
        total_replicas = status.replicas or 0
        ready_replicas = status.ready_replicas or 0
        available_replicas = status.available_replicas or 0
        
        # Determine overall health
        if total_replicas > 0 and ready_replicas == total_replicas:
            health_color = 'green'
            health_status = "Healthy"
        else:
            health_color = 'yellow'
            health_status = "Progressing"

        click.echo(click.style(f"\n--- Deployment Status: {name} ---", bold=True))
        click.echo(f"  Namespace: {namespace}")
        click.echo(f"  Health:    {click.style(health_status, fg=health_color)}")
        click.echo(f"  Replicas:  {ready_replicas}/{total_replicas} Ready")
        
        # 2. Get Pod Statuses
        click.echo("\n  --- Pods ---")
        # Find pods that belong to this deployment using labels
        label_selector = f"app={name}"
        pod_list = core_api.list_namespaced_pod(namespace=namespace, label_selector=label_selector)

        if not pod_list.items:
            click.echo("  No pods found for this deployment.")
            return

        for pod in pod_list.items:
            pod_name = pod.metadata.name
            pod_phase = pod.status.phase
            
            if pod_phase == "Running":
                pod_color = 'green'
            elif pod_phase == "Pending":
                pod_color = 'yellow'
            else:
                pod_color = 'red'
                
            click.echo(f"  - {pod_name}  (Status: {click.style(pod_phase, fg=pod_color)})")

    except client.ApiException as e:
        if e.status == 404:
            click.echo(click.style(f"Error: Deployment '{name}' not found in namespace '{namespace}'.", fg='red'), err=True)
        else:
            click.echo(click.style(f"API Error getting status: {e.reason}", fg='red'), err=True)
    except Exception as e:
        click.echo(click.style(f"An unexpected error occurred: {e}", fg='red'), err=True)
