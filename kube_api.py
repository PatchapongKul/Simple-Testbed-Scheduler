from kubernetes import client, config

# Load kubeconfig
config.load_kube_config()

# Create API client
v1 = client.CoreV1Api()

# List nodes and their resources
nodes = v1.list_node()

for node in nodes.items:
    node_name = node.metadata.name
    allocatable = node.status.allocatable
    print(f"Node: {node_name}")
    print(f"Allocatable Resources: {node.status}")
