# k8s_automation/deployment.py
import yaml
from jinja2 import Environment, FileSystemLoader
from kubernetes import client
import click
import os

def validate_and_process_values(values_path):
    """Loads a YAML values file, validates it, and provides defaults."""
    try:
        with open(values_path, 'r') as f:
            user_values = yaml.safe_load(f)
            if not isinstance(user_values, dict):
                click.echo(click.style("YAML file must contain a dictionary.", fg='red'), err=True)
                return None
    except Exception as e:
        click.echo(click.style(f"Error reading or parsing YAML file: {e}", fg='red'), err=True)
        return None

    # --- Deployment Validation ---
    required_fields = ['name', 'image']
    for field in required_fields:
        if field not in user_values:
            click.echo(click.style(f"Missing required field in values file: '{field}'", fg='red'), err=True)
            return None

    # --- Scaling Validation ---
    if 'scaling' in user_values:
        scaling_values = user_values['scaling']
        if not isinstance(scaling_values, dict):
            click.echo(click.style("The 'scaling' key must contain a dictionary.", fg='red'), err=True)
            return None
        
        required_scaling_fields = ['trigger_type', 'trigger_metadata']
        for field in required_scaling_fields:
            if field not in scaling_values:
                click.echo(click.style(f"Missing required field in 'scaling' section: '{field}'", fg='red'), err=True)
                return None
    
    # --- Set Defaults ---
    defaults = {
        'namespace': 'default', 'port': 80, 'replicas': 1,
        'cpu_request': '100m', 'mem_request': '128Mi',
        'cpu_limit': '250m', 'mem_limit': '256Mi'
    }
    final_values = defaults.copy()
    final_values.update(user_values)
    
    return final_values

def create_kubernetes_resources(api_client: client.ApiClient, values: dict):
    """Renders and applies Deployment and ScaledObject from a values dictionary."""
    template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
    env = Environment(loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True)
    
    # Initialize specific API clients from the base api_client
    apps_api = client.AppsV1Api(api_client)
    custom_api = client.CustomObjectsApi(api_client)

    try:
        # --- 1. Apply Deployment ---
        click.echo("\n--- Preparing Deployment ---")
        deployment_template = env.get_template('deployment.yaml.j2')
        rendered_deployment_str = deployment_template.render(**values)
        click.echo(click.style(rendered_deployment_str, fg='yellow'))
        deployment_obj = yaml.safe_load(rendered_deployment_str)
        
        try:
            apps_api.read_namespaced_deployment(name=values['name'], namespace=values['namespace'])
            click.echo(f"-> Deployment '{values['name']}' already exists. Patching...")
            apps_api.patch_namespaced_deployment(name=values['name'], namespace=values['namespace'], body=deployment_obj)
            click.echo(click.style(f"Deployment '{values['name']}' patched.", fg='green'))
        except client.ApiException as e:
            if e.status == 404:
                click.echo(f"-> Deployment '{values['name']}' not found. Creating...")
                apps_api.create_namespaced_deployment(namespace=values['namespace'], body=deployment_obj)
                click.echo(click.style(f"Deployment '{values['name']}' created.", fg='green'))
            else:
                raise

        # --- 2. Apply ScaledObject (if scaling info is present) ---
        if 'scaling' in values:
            click.echo("\n--- Preparing ScaledObject ---")
            so_template = env.get_template('scaledobject.yaml.j2')
            rendered_so_str = so_template.render(**values)
            click.echo(click.style(rendered_so_str, fg='cyan'))
            so_obj = yaml.safe_load(rendered_so_str)
            
            so_name = f"{values['name']}-so"
            group = 'keda.sh'
            version = 'v1alpha1'
            plural = 'scaledobjects'
            
            try:
                custom_api.get_namespaced_custom_object(group=group, version=version, namespace=values['namespace'], plural=plural, name=so_name)
                click.echo(f"-> ScaledObject '{so_name}' already exists. Patching...")
                custom_api.patch_namespaced_custom_object(group=group, version=version, namespace=values['namespace'], plural=plural, name=so_name, body=so_obj)
                click.echo(click.style(f"ScaledObject '{so_name}' patched.", fg='green'))
            except client.ApiException as e:
                if e.status == 404:
                    click.echo(f"-> ScaledObject '{so_name}' not found. Creating...")
                    custom_api.create_namespaced_custom_object(group=group, version=version, namespace=values['namespace'], plural=plural, body=so_obj)
                    click.echo(click.style(f"ScaledObject '{so_name}' created.", fg='green'))
                else:
                    raise

    except client.ApiException as e:
        click.echo(click.style(f"API Error during resource application: {e.reason}", fg='red'), err=True)
        return False, None
    except Exception as e:
        click.echo(click.style(f"An unexpected error occurred: {e}", fg='red'), err=True)
        return False, None

    return True, values # Return success and the values for the summary
