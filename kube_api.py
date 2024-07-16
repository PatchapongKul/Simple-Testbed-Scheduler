from kubernetes import client, config, watch
from kubernetes.client import V1ObjectReference, V1ObjectMeta

# Load kubeconfig from the specified path
kubeconfig_path = '/etc/rancher/k3s/k3s.yaml'
config.load_kube_config(config_file=kubeconfig_path)

# Create API client
v1 = client.CoreV1Api()

def schedule_pod(pod, node_name):
    print(f"Attempting to schedule pod {pod.metadata.name} to node {node_name}")
    
    target = V1ObjectReference(
        api_version="v1",
        kind="Node",
        name=node_name,
        namespace="default"
    )
    
    print(f"Target: {target}")
    
    binding = client.V1Binding(
        api_version="v1",
        kind="Binding",
        target=target,
        metadata=V1ObjectMeta(name=pod.metadata.name)
    )
    
    print(f"Binding object: {binding}")

    try:
        v1.create_namespaced_pod_binding(name=pod.metadata.name, namespace=pod.metadata.namespace, body=binding)
        print(f"Pod {pod.metadata.name} scheduled to node {node_name}")
    except client.exceptions.ApiException as e:
        print(f"Error binding pod: {e}")
        print(f"Pod metadata: {pod.metadata}")
        print(f"Target node: {node_name}")

def main():
    w = watch.Watch()
    for event in w.stream(v1.list_namespaced_pod, namespace='default'):
        pod = event['object']
        if pod.status.phase == 'Pending':
            # Check if pod has necessary metadata
            if not pod.metadata or not pod.metadata.name or not pod.metadata.namespace:
                print("Pod metadata is missing or incomplete.")
                continue
            
            # Retrieve resource requests (CPU and memory) from the first container
            if pod.spec.containers and pod.spec.containers[0].resources and pod.spec.containers[0].resources.requests:
                cpu_request = pod.spec.containers[0].resources.requests.get('cpu')
                memory_request = pod.spec.containers[0].resources.requests.get('memory')
                print(f"Pod name: {pod.metadata.name}")
                print(f"CPU Request: {cpu_request}")
                print(f"Memory Request: {memory_request}")
                schedule_pod(pod, "cillium3")
            else:
                print(f"Resource requests not found for pod {pod.metadata.name}")

if __name__ == "__main__":
    main()

