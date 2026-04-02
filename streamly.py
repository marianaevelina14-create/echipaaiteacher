import streamlit as st
import logging
import json
import requests
import base64
import time
from PIL import Image, ImageEnhance
from openai import OpenAI, OpenAIError
from supabase import create_client

# =========================
# CONFIG
# =========================

logging.basicConfig(level=logging.INFO)

OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
ASSISTANT_ID = st.secrets["OPENAI_ASSISTANT_ID"]

client = OpenAI(api_key=OPENAI_API_KEY)

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

NUMBER_OF_MESSAGES_TO_DISPLAY = 20


# =========================
# SESSION STATE
# =========================

def initialize_session_state():
    if "history" not in st.session_state:
        st.session_state["history"] = []

    if "conversation_history" not in st.session_state:
        st.session_state["conversation_history"] = []

    if "thread_id" not in st.session_state:
        st.session_state["thread_id"] = None


# =========================
# SUPABASE
# =========================

def save_to_supabase(user_message, bot_message):
    try:
        supabase.table("messages").insert({
            "user_message": user_message,
            "bot_response": bot_message
        }).execute()
    except Exception as e:
        logging.error(f"Supabase error: {e}")


# =========================
# THREAD HANDLER
# =========================

def get_or_create_thread():
    if not st.session_state.thread_id:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
    return st.session_state.thread_id


# =========================
# LOAD UPDATES
# =========================

def load_streamlit_updates():
    try:
        with open("data/streamlit_updates.json", "r") as f:
            return json.load(f)
    except:
        return {}


# =========================
# CHAT LOGIC
# =========================

def on_chat_submit(chat_input, latest_updates):
    user_input = chat_input.strip()

    try:
        assistant_reply = ""

        # CASE 1: updates
        if "latest updates" in user_input.lower():
            highlights = latest_updates.get("Highlights", {})
            assistant_reply = "Here are the latest updates:\n"

            for version, info in highlights.items():
                description = info.get("Description", "")
                assistant_reply += f"- {version}: {description}\n"

        # CASE 2: OpenAI Assistant
        else:
            thread_id = get_or_create_thread()

            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=user_input
            )

            run = client.beta.threads.runs.create_and_poll(
                thread_id=thread_id,
                assistant_id=ASSISTANT_ID,
                tools=[{"type": "file_search"}],
            )

            if run.status != "completed":
                raise OpenAIError(f"Run status: {run.status}")

            messages = client.beta.threads.messages.list(
                thread_id=thread_id,
                order="desc",
                limit=10
            )

            assistant_reply = "No response from assistant."

            for msg in messages.data:
                if msg.role == "assistant":
                    for content in msg.content:
                        if content.type == "text":
                            assistant_reply = content.text.value
                            break
                    break

        # SAVE HISTORY
        st.session_state["history"].append({
            "role": "user",
            "content": user_input
        })

        st.session_state["history"].append({
            "role": "assistant",
            "content": assistant_reply
        })

        # SAVE SUPABASE
        save_to_supabase(user_input, assistant_reply)

    except OpenAIError as e:
        logging.error(e)
        st.error(f"OpenAI error: {e}")

    except Exception as e:
        logging.error(e)
        st.error(f"Error: {e}")


# =========================
# STREAMLIT UI
# =========================

def main():
    st.set_page_config(
        page_title="AI Teacher Web App",
        page_icon="imgs/logo.jpg",
        layout="wide"
    )

    initialize_session_state()

    # ===== CHAT INPUT =====
    chat_input = st.chat_input("Întreabă-ți profesorul AI orice...")

    if chat_input:
        latest_updates = load_streamlit_updates()
        on_chat_submit(chat_input, latest_updates)

    # ===== CHAT DISPLAY =====
    for msg in st.session_state["history"][-NUMBER_OF_MESSAGES_TO_DISPLAY:]:
        avatar = "imgs/logo.jpg" if msg["role"] == "assistant" else "👤"

        with st.chat_message(msg["role"], avatar=avatar):
            st.write(msg["content"])


# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()
