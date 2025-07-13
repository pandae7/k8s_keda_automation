# Kubernetes Automation CLI

A command-line tool to simplify and automate common Kubernetes deployment and management tasks, with a focus on setting up event-driven autoscaling using KEDA.

## Overview

This tool provides a streamlined workflow for developers and operators to:

- Verify connectivity to a Kubernetes cluster.
- Install and manage tooling like KEDA using Helm.
- Deploy applications from version-controlled configuration files.
- Automatically configure KEDA ScaledObjects for event-driven autoscaling.
- Check the health and status of deployments.

## Prerequisites

Before you begin, ensure you have the following installed and configured:

- **Python 3.8+ and pip**
- **kubectl**: Configured to connect to your target Kubernetes cluster. You can verify this by running:
  ```sh
  kubectl cluster-info
  ```
- **Helm**: for handling keda helm charts
- **Git**: For cloning the repository.

## Installation

Clone the repository:

```sh
git clone https://github.com/pandae7/k8s_keda_automation.git
cd k8s-automation-cli
```

Create a virtual environment (recommended):

```sh
python3 -m venv venv
source venv/bin/activate
```

Install the required Python packages:

```sh
pip install -r requirements.txt
```

## Usage

The CLI is invoked through `main.py`. You can get a list of all commands by running:

```sh
python main.py --help
```

### Global Options

- `--context <CONTEXT_NAME>`: Specify a Kubernetes context to use for any command. This overrides your current default context.

## Available Commands
check-connection
install-tools
create-deployment
get-status

### check-connection

Verifies that the CLI can successfully connect to your Kubernetes cluster using your current kubeconfig and context.

**Usage:**
```sh
# Check connection using the default context
python main.py check-connection

# Check connection using a specific context
python main.py --context my-staging-cluster check-connection
```

### install-tools

Installs KEDA (Kubernetes Event-driven Autoscaling) onto your cluster using its official Helm chart. It will attempt to install Helm if it's not found on Linux/macOS.

**Usage:**
```sh
# Install KEDA into the default cluster context
python main.py install-tools

# Install KEDA into a specific cluster context
python main.py --context my-production-cluster install-tools
```

### create-deployment

Deploys an application along with its KEDA autoscaling configuration using a YAML values file. This is the primary command for deploying workloads.

**Usage:**
```sh
python main.py create-deployment --values <path/to/your/values.yaml>
```

**Example `values.yaml`:**

This example deploys a worker application that scales based on a Kafka topic's consumer lag.

```yaml
# my-app-values.yaml

# --- Deployment Configuration ---
name: kafka-console-consumer
image: confluentinc/cp-kafka:7.3.0
namespace: kafka
replicas: 3

# --- KEDA Scaling Configuration (Optional) ---
scaling:
  trigger_type: kafka
  min_replicas: 0
  max_replicas: 15
  trigger_metadata:
    bootstrapServers: "kafka-svc.kafka.svc.cluster.local:9092"
    topic: "my-test-topic"
    consumerGroup: "test-consumer-group"
    lagThreshold: "10"
```

### get-status

Fetches and displays the current health and status of a deployment and its associated pods.

**Usage:**
```sh
python main.py get-status <DEPLOYMENT_NAME> --namespace <NAMESPACE>
```

**Example:**
```sh
# Check the status of the deployment created in the example above
python main.py get-status kafka-console-consumer --namespace kafka
```

**Example Output:**
```
--- Deployment Status: kafka-console-consumer ---
  Namespace: workers
  Health:    Healthy
  Replicas:  3/3 Ready
  --- Pods ---
  - kafka-console-consumer-5f7b8c9d4-abcde  (Status: Running)
  - kafka-console-consumer-5f7b8c9d4-fghij  (Status: Running)
  - kafka-console-consumer-5f7b8c9d4-klmno  (Status: Running)
```

## End-to-End Testing with Kafka

This section guides you through a complete test of the event-driven scaling functionality.

### 1. Set up Kafka namespace and Broker

First, Create a new namespace for kafka

```sh
kubectl create namespace kafka
```

Now we will create the kafka deployment file:

```yaml
#kafka-deployment.yml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: kafka
  namespace: kafka
  labels:
    app: kafka-app
spec:
  serviceName: kafka-svc
  replicas: 3
  selector:
    matchLabels:
      app: kafka-app
  template:
    metadata:
      labels:
        app: kafka-app
    spec:
      containers:
        - name: kafka-container
          image: doughgle/kafka-kraft
          ports:
            - containerPort: 9092
            - containerPort: 9093
          env:
            - name: REPLICAS
              value: '3'
            - name: SERVICE
              value: kafka-svc
            - name: NAMESPACE
              value: kafka
            - name: SHARE_DIR
              value: /mnt/kafka
            - name: My_CLUSTER_ID
              value: <insert_Secret_id>
            - name: DEFAULT_REPLICATION_FACTOR
              value: '3'
            - name: DEFAULT_MIN_INSYNC_REPLICAS
              value: '2'
          volumeMounts:
            - name: data
              mountPath: /mnt/kafka
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes:
          - "ReadWriteOnce"
        resources:
          requests:
            storage: "1Gi"
---
apiVersion: v1
kind: Service
metadata:
  name: kafka-svc
  namespace: kafka
  labels:
    app: kafka-app
spec:
  type: NodePort
  ports:
    - name: '9092'
      port: 9092
      protocol: TCP
      targetPort: 9092
      nodePort: 30092
  selector:
    app: kafka-app

```

create the deployment using 

```sh
kubectl apply -f kafka-deployment.yml
```


Wait for the `my-kafka-0/1/2` pod to be in the Running state before proceeding.

### 2. Prepare the Consumer Values File

Create a file named `kafka-consumer-values.yaml`. This uses a public image with Kafka tools and overrides its command to run a consumer.

```yaml
# kafka-consumer-values.yaml
name: kafka-console-consumer
image: confluentinc/cp-kafka:7.3.0
namespace: kafka
replicas: 1
command:
  - "/bin/sh"
  - "-c"
  - "echo 'Starting consumer...'; kafka-console-consumer --bootstrap-server kafka-svc.kafka.svc.cluster.local:9092 --topic my-test-topic --group test-consumer-group | while read line; do echo hi; sleep 0.01; done"
scaling:
  trigger_type: kafka
  min_replicas: 0
  max_replicas: 10
  trigger_metadata:
    bootstrapServers: "kafka-svc.kafka.svc.cluster.local:9092"
    topic: "my-test-topic"
    consumerGroup: "test-consumer-group"
    lagThreshold: "10"
```

### 3. Deploy the Consumer Application

Use the CLI to deploy the consumer and its KEDA ScaledObject.

```sh
python main.py create-deployment --values kafka-consumer-values.yaml
```

### 4. Produce Messages to Trigger Scaling

get a command line in one of the brokers with:

```sh
kubectl exec -it kafka-0 -n kafka -- bash
```

From inside the producer's shell, create the topic and send few messages to it. This will exceed the `lagThreshold` of 10.

```sh
# Create the topic
kafka-topics.sh --create --topic my-test-topic --bootstrap-server kafka-svc:9092

# Produce 150000 messages
for i in {1..150000}; do echo "test message $i"; done | kafka-console-consumer.sh --bootstrap-server kafka-svc:9092 --topic my-topic
# Exit the producer pod
exit
```

### 5. Observe the Autoscaling

In your local terminal, watch the consumer deployment. You will see KEDA scale the pods up from 0 to 1 (or more) to handle the load.

```sh
kubectl get deployment kafka-console-consumer --watch
```

After the messages are consumed, KEDA will scale the deployment back down to 0 after the cooldown period.

### 6. Cleanup

When you're done, remove the test resources.

```sh
kubectl delete deployment kafka-console-consumer
kubectl delete scaledobject kafka-console-consumer-so
kubectl delete deployment kafka-app
```

### References - 
For Kafka Broker, Producer and Consumer - https://medium.com/@martin.hodges/deploying-kafka-on-a-kind-kubernetes-cluster-for-development-and-testing-purposes-ed7adefe03cb

For Kafka and Keda scaling Object - https://keda.sh/docs/2.5/scalers/apache-kafka/
