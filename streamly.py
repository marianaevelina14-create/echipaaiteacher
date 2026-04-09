

import streamlit as st
import logging
from PIL import Image, ImageEnhance
import time
import json
import requests
import base64
from datetime import datetime, timedelta
from openai import OpenAI, OpenAIError
from supabase import create_client
# Configure logging
logging.basicConfig(level=logging.INFO)

# Constants
NUMBER_OF_MESSAGES_TO_DISPLAY = 20
API_DOCS_URL = "https://docs.streamlit.io/library/api-reference"

# Retrieve and validate API key
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", None)


if not OPENAI_API_KEY:
    st.error("Please add your OpenAI API key to the Streamlit secrets.toml file.")
    st.stop()

# Assign OpenAI API Key
#openai.api_key = OPENAI_API_KEY
#client = openai.OpenAI()

# Create OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)
ASSISTANT_ID = st.secrets["OPENAI_ASSISTANT_ID"]


SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_message(session_id, role, content):
    try:
        response = supabase.table("messages").insert({
            "session_id": session_id,
            "role": role,
            "content": content,
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        # IMPORTANT: verificare eroare
        if response.data is None:
            st.error(f"Supabase insert failed: {response}")

        return response

    except Exception as e:
        st.error(f"Supabase error: {str(e)}")
        return None



def load_messages(session_id):
    res = supabase.table("messages") \
        .select("*") \
        .eq("session_id", session_id) \
        .order("created_at") \
        .execute()
    return res.data


def get_or_create_thread():
    if not st.session_state.thread_id:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
    return st.session_state.thread_id


# =========================
# SESSION INIT
# =========================

def get_latest_update_from_json(keyword, latest_updates):
    for section in ["Highlights", "Notable Changes", "Other Changes"]:
        for sub_key, sub_value in latest_updates.get(section, {}).items():
            for key, value in sub_value.items():
                if keyword.lower() in key.lower() or keyword.lower() in value.lower():
                    return f"Section: {section}\nSub-Category: {sub_key}\n{key}: {value}"
    return "No updates found for the specified keyword."
def is_inappropriate(text):
    bad_words = ["prost", "idiot", "stupid", "dracu"]
    return any(word == text.lower().strip() for word in bad_words)


def is_apology(text):
    return text.lower().strip() in [
        "scuze",
        "îmi cer scuze",
        "îmi pare rău"
    ]

def on_chat_submit(user_input):

    user_input = user_input.strip()

    # 1. DACA E BLOCAT
    if st.session_state.chat_status == "blocked":
        st.error("⛔ Chat blocat. Cereți scuze și revino la lecție.")
        
        if is_apology(user_input):
            st.session_state.chat_status = "active"
            st.session_state.bad_count = 0
            st.success("🟢 Chat deblocat")
        
        return

    st.session_state.history.append({"role": "user", "content": user_input})

    try:
        thread_id = get_or_create_thread()

        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_input
        )

        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID
        )

        # =========================
        # WAIT LOOP (CORECT ÎN FUNCȚIE)
        # =========================
        start_time = time.time()

        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )

            if run_status.status == "completed":
                break

            if run_status.status in ["failed", "cancelled", "expired"]:
                raise Exception(run_status.status)

            if time.time() - start_time > 30:
                raise Exception("timeout")

            time.sleep(0.5)

        messages = client.beta.threads.messages.list(
            thread_id=thread_id,
            order="desc",
            limit=10
        )

        reply = "Nu am primit răspuns."

        for msg in messages.data:
            if msg.role == "assistant":
                parts = [c.text.value for c in msg.content if c.type == "text"]
                if parts:
                    reply = "\n".join(parts)
                    break

        st.session_state.history.append({"role": "assistant", "content": reply})

    except Exception as e:
        st.error(f"Eroare: {str(e)}")
def initialize_session_state():
    import uuid

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "history" not in st.session_state:
        st.session_state.history = []

    if "bad_count" not in st.session_state:
        st.session_state.bad_count = 0

    if "chat_status" not in st.session_state:
        st.session_state.chat_status = "active"

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
def render_sidebar():
    st.sidebar.title("AI Teacher")
    st.sidebar.write("Asistent educațional AI")

    st.sidebar.markdown("### Materii")
    st.sidebar.write("Română")
def main():
    initialize_session_state()
    render_sidebar()

    if st.session_state.chat_status == "blocked":
        st.warning("⛔ Chat blocat. Scrie scuze.")

        apology_input = st.text_input("Scrie scuze aici:")

        if apology_input:
            if is_apology(apology_input):
                st.session_state.chat_status = "active"
                st.session_state.bad_count = 0
                st.success("Deblocat!")
                st.rerun()
            else:
                st.error("Nu e scuză validă.")

        return

    chat_input = st.chat_input("Întreabă AI")

    if chat_input:
        on_chat_submit(chat_input)

    for msg in st.session_state.history[-NUMBER_OF_MESSAGES_TO_DISPLAY:]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])


if __name__ == "__main__":
    main()
