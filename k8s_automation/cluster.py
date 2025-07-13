from kubernetes import client, config
import click

def connect_to_cluster(context=None):
    """Loads kubeconfig and returns a Kubernetes API client."""
    try:
        # Pass the context to the config loader
        config.load_kube_config(context=context)
        api = client.CoreV1Api()
        return api
    except config.ConfigException as e:
        click.echo(f"Error: Could not load kubeconfig or context. {e}", err=True)
        return None
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        return None
