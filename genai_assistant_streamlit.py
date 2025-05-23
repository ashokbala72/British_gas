import os
from dotenv import load_dotenv
import streamlit as st
from openai import OpenAI

# Load environment variables from .env
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Check if API key was loaded
if not api_key:
    st.error("❌ OpenAI API Key not found. Please create a .env file with OPENAI_API_KEY.")
    st.stop()

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

# Page configuration
st.set_page_config(page_title="British Gas GenAI Assistant", layout="wide")
st.title("British Gas GenAI Assistant")

# Create two tabs
customer_tab, agent_tab = st.tabs(["Customer Assistant", "Agent Assistant"])

# Real-time LLM response function using GPT-4
def generate_response(query, role):
    system_prompt = (
        "You are a helpful assistant for British Gas customers. Provide friendly, concise answers about bills, meters, or energy usage."
        if role == "customer"
        else "You are a diagnostic assistant for British Gas agents. Offer step-by-step resolution guidance for customer-reported issues."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.6
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Error generating response: {str(e)}"

# Customer Assistant Tab
with customer_tab:
    st.header("🔹 Customer Self-Service Assistant")
    customer_query = st.text_input("Ask a question about your bill, meter, or supply:")
    if customer_query:
        response = generate_response(customer_query, "customer")
        st.markdown("### Response")
        st.success(response)

# Agent Assistant Tab
with agent_tab:
    st.header("🔸 Agent Diagnostic Copilot")
    agent_query = st.text_input("Enter issue reported by customer:")
    if agent_query:
        response = generate_response(agent_query, "agent")
        st.markdown("### Suggested Diagnostic Steps")
        st.info(response)

# Sidebar Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**Powered by OpenAI GPT-4**")
st.sidebar.markdown("Version 1.0 Live Prototype")
