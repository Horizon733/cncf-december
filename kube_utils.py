from kubernetes import client, config

def get_pod_logs(namespace, pod_name, container_name):
    config.load_kube_config()
    v1 = client.CoreV1Api()
    logs = v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, container=container_name)
    return logs

# pip install streamlit langchain-community ollama beautifulsoup4
