import subprocess
import shutil
import click
from kubernetes import client
import time
import platform

def ensure_helm_installed():
    """Checks if Helm is installed, and if not, attempts to install it."""
    click.echo("-> Checking for Helm installation...")
    if shutil.which("helm"):
        click.echo(click.style("Helm is already installed.", fg='green'))
        return True

    click.echo("Helm not found. Attempting to install...")
    
    # The official install script is primarily for Linux/macOS.
    if platform.system() == "Windows":
        click.echo(click.style("Automatic installation on Windows is not supported.", fg='yellow'), err=True)
        click.echo("Please install Helm manually from: https://helm.sh/docs/intro/install/", err=True)
        return False

    try:
        # Use the official 'get-helm-3' script
        install_script = "curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 && chmod 700 get_helm.sh && ./get_helm.sh && rm get_helm.sh"
        subprocess.run(install_script, shell=True, check=True, capture_output=True, text=True)
        click.echo(click.style("✓ Helm installed successfully.", fg='green'))
        
        # Verify after install
        if not shutil.which("helm"):
            click.echo(click.style("Installation ran, but 'helm' is not in the system PATH.", fg='yellow'), err=True)
            click.echo("You may need to restart your shell or update your PATH environment variable.", err=True)
            return False
        return True

    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"✗ Failed to install Helm using script: {e.stderr}", fg='red'), err=True)
        return False
    except FileNotFoundError:
        click.echo(click.style(f"✗ Failed to install Helm: 'curl' command not found.", fg='red'), err=True)
        return False

def run_command(command, description):
    """Runs a shell command and handles errors."""
    try:
        click.echo(f"-> Running: '{description}'...")
        subprocess.run(command, check=True, shell=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"Error during '{description}': {e.stderr}", fg='red'), err=True)
        return False

def add_helm_repo():
    """Adds and updates the KEDA Helm repository."""
    if not run_command("helm repo add kedacore https://kedacore.github.io/charts", "Add KEDA Helm repo"):
        return False
    if not run_command("helm repo update", "Update Helm repos"):
        return False
    return True

def install_keda_chart():
    """Installs the KEDA Helm chart into the 'keda' namespace."""
    command = "helm upgrade --install keda kedacore/keda --namespace keda --create-namespace"
    return run_command(command, "Install KEDA chart")

def verify_keda_installation(api_client: client.AppsV1Api):
    """Verifies that the KEDA operator deployment is running and ready."""
    click.echo("-> Verifying KEDA installation...")
    retries = 12
    delay = 10  # seconds
    for i in range(retries):
        try:
            deployment = api_client.read_namespaced_deployment(name="keda-operator", namespace="keda")
            # Check if the deployment is ready
            if (deployment.status.ready_replicas is not None and
                    deployment.status.ready_replicas > 0):
                click.echo(click.style("KEDA operator deployment is running and ready.", fg='green'))
                return True
            else:
                click.echo(f"KEDA operator deployment found, but not ready yet. Retrying in {delay}s...")
        except client.ApiException as e:
            if e.status == 404:
                click.echo(f"KEDA operator deployment not found yet. Retrying in {delay}s... ({i+1}/{retries})")
            else:
                click.echo(click.style(f"API Error verifying KEDA: {e}", fg='red'), err=True)
                return False
        
        time.sleep(delay)
    
    click.echo(click.style("Verification failed: KEDA operator deployment did not become ready in time.", fg='red'), err=True)
    return False
