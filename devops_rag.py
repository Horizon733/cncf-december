import streamlit as st
from langchain.llms import Ollama
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.tools import Tool
from kubernetes import client, config
import requests
from bs4 import BeautifulSoup

# Constants
PROMPT_TEMPLATE = """
You are a knowledgeable assistant who can answer questions about DevOps and fetch information from the web.
If the user greets, respond with a greeting. If the user asks a question, provide a concise and relevant answer.
Use the following context for answering questions:

{context}

Conversation History: 
{history}

---

Answer the question based on the above context: {query}
"""

# 1. Define Ollama LLM
ollama_llm = Ollama(base_url="http://localhost:11434", model="llama3.1")

# Memory for conversation history
memory = ConversationBufferMemory(
    memory_key="history", 
    return_messages=True,
    input_key="query",
)

# Prompt Template for LangChain
prompt_template = PromptTemplate(
    input_variables=["context", "history", "query"],
    template=PROMPT_TEMPLATE
)

chain = LLMChain(llm=ollama_llm, prompt=prompt_template, memory=memory)
context = ""

# 2. Define tools
# Tool 1: Real-Time Web Search
def web_search(query, max_results=5):
    url = f"https://duckduckgo.com/html/?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for link in soup.find_all("a", class_="result__a", limit=max_results):
        results.append(link.get("href"))
    return results

web_search_tool = Tool(
    name="WebSearch",
    func=lambda query: web_search(query),
    description="Search the web for relevant information."
)

# Tool 2: Kubernetes Log Fetching
def get_pod_logs(pod_name, namespace="default", container_name=None, tail_lines=100):
    try:
        config.load_kube_config()
        v1 = client.CoreV1Api()
        logs = v1.read_namespaced_pod_log(
            name=pod_name, namespace=namespace,
            container=container_name, tail_lines=tail_lines
        )
        return logs
    except Exception as e:
        return f"Error fetching logs: {e}"
    

def get_pods(namespace="default"):
    try:
        config.load_kube_config()
        v1 = client.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace=namespace)
        return [pod.metadata.name for pod in pods.items]
    except Exception as e:
        return f"Error fetching pods: {e}"

# 3. Streamlit UI
st.title("Kubernetes Management with LangChain and Ollama")
st.sidebar.header("Settings")

# Sidebar option to upload log files
st.sidebar.subheader("Upload Log Files")
uploaded_file = st.sidebar.file_uploader("Choose a log file", type=["txt"])

if uploaded_file is not None:
    uploaded_log_content = uploaded_file.getvalue().decode("utf-8")
    st.sidebar.write("### Uploaded Log File Content:")
    st.sidebar.text_area("Logs", uploaded_log_content, height=300)
else:
    uploaded_log_content = None

# Section 2: Chat Interface
st.subheader("Chat with Ollama")
chat_container = st.container()

# Function to display chat messages
def display_message(message, is_user=True):
    if is_user:
        chat_container.markdown(f"<div style='text-align: right; padding: 10px; border-radius: 10px; margin: 5px;'>{message}</div>", unsafe_allow_html=True)
    else:
        chat_container.markdown(f"<div style='text-align: left; padding: 10px; border-radius: 10px; margin: 5px;'>{message}</div>", unsafe_allow_html=True)

# Initialize chat history and selected pod in session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_pod" not in st.session_state:
    st.session_state.selected_pod = None

# Display chat history
with chat_container:
    for chat in st.session_state.messages:
        display_message(chat['content'], is_user=chat['is_user'])

chat_input = st.text_input("Enter your message:")

# Main area for Pod Logs Search
st.subheader("Pod Logs Search")
show_pod_logs_search = st.checkbox("Enable Pod Logs Search")

if show_pod_logs_search:
    st.subheader("Pod Logs Search Settings")
    namespace_for_logs = st.text_input("Namespace (optional):", "default")
    
    # Fetch pods for radio buttons
    if st.button("Fetch Pods for Logs"):
        with st.spinner("Fetching pods..."):
            all_pods_for_logs = get_pods(namespace_for_logs)
            if isinstance(all_pods_for_logs, list):
                st.session_state.selected_pod = st.radio("Select Pod:", all_pods_for_logs, index=all_pods_for_logs.index(st.session_state.selected_pod) if st.session_state.selected_pod in all_pods_for_logs else 0)

    if st.session_state.selected_pod:
        st.write(f"Selected Pod: {st.session_state.selected_pod}")

    if st.button("Reset Pod Selection"):
        st.session_state.selected_pod = None

if st.button("Send"):
    if chat_input:
        with st.spinner("Generating response..."):
            if uploaded_log_content:
                context += f"\nUploaded Log Content:\n{uploaded_log_content}\n"
            elif show_pod_logs_search and st.session_state.selected_pod:
                pod_logs = get_pod_logs(st.session_state.selected_pod, namespace_for_logs)
                context += f"\nPod Logs:\n{pod_logs}\n"
            else:
                context += f"\nWeb search result:\n{web_search_tool.run(chat_input)}\n"
            
            chat_response = chain.run(context=context, query=chat_input, history=st.session_state.messages)
            
        # Update conversation memory
        st.session_state.messages.append({"role": "user", "content": chat_input, "is_user":True})
        st.session_state.messages.append({"role": "assistant", "content": chat_response, "is_user":False})
        st.rerun() 
    else:
        st.warning("Please enter a message!")