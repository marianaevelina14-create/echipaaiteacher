

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



def unblock_chat(session_id):
    supabase.table("chat_limits").upsert({
        "session_id": session_id,
        "blocked": True
    }).execute()



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

    # 🔒 HARD BLOCK
    if st.session_state.chat_status == "blocked":

        if is_apology(user_input):
            st.session_state.chat_status = "active"
            st.session_state.bad_count = 0
            st.success("🟢 Chat deblocat")
            return

        # ❗ ACELAȘI MESAJ MEREU
        st.error("⛔ Chat blocat. Cereți scuze și revino la lecție.")
        return

    # ⚠️ BAD WORD CHECK
    if is_inappropriate(user_input):

        st.session_state.bad_count += 1

        if st.session_state.bad_count == 1:
            st.warning("Te rog să folosești un limbaj respectuos pentru a putea continua.")
            return

        elif st.session_state.bad_count == 2:
            st.warning("Te rog să ai grijă la limbaj. Dacă vei continua, conversația va fi restricționată.")
            return

        elif st.session_state.bad_count >= 3:
            st.session_state.chat_status = "blocked"
            st.error("⛔ Chat blocat. Cereți scuze și revino la lecție.")
            return

    # ✅ FLOW NORMAL
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

        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )

            if run_status.status == "completed":
                break

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

    # SESSION ID
    if "session_id" not in st.session_state:
        st.session_state.session_id = st.query_params.get("session_id", None)

    if not st.session_state.session_id:
        st.session_state.session_id = str(uuid.uuid4())
        st.query_params["session_id"] = st.session_state.session_id
    if "warning_stage" not in st.session_state:
        st.session_state.warning_stage = 0
    # CHAT HISTORY
    if "history" not in st.session_state:
        st.session_state.history = []

    # MODERATION
    if "bad_count" not in st.session_state:
        st.session_state.bad_count = 0

    if "chat_status" not in st.session_state:
        st.session_state.chat_status = "active"

    # OPENAI THREAD
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
def render_sidebar():
    st.sidebar.title("AI Teacher")
    st.sidebar.write("Asistent educațional AI")

    st.sidebar.markdown("### Materii")
    st.sidebar.write("Română")
    

# =========================
# MAIN
# =========================
def main():
    initialize_session_state()

    # =========================
    # STATUS UI
    # =========================
    status_placeholder = st.empty()

    with status_placeholder.container():
        if st.session_state.chat_status == "warning":
            st.warning(f"⚠️ {st.session_state.warning_stage}/3 jigniri")

        elif st.session_state.chat_status == "blocked":
            st.error("⛔ Chat blocat 5 minute. Cere scuze pentru deblocare.")

        else:
            st.success("🟢 Chat activ")

    # =========================
    # CHECK BLOCK STATUS
    # =========================
    blocked = st.session_state.chat_status == "blocked"

    if blocked:
        st.warning("⛔ Chat blocat 5 minute. Scrie scuze pentru deblocare.")

        apology_input = st.text_input("Scrie scuze aici:")

        if apology_input:
            if is_apology(apology_input):

                supabase.table("chat_limits") \
                    .delete() \
                    .eq("session_id", st.session_state.session_id) \
                    .execute()

                st.session_state.bad_count = 0
                st.session_state.chat_status = "active"

                st.success("✅ Chat deblocat!")
                st.rerun()

            else:
                st.error("❌ Nu este o scuză validă.")

    else:
        # =========================
        # CHAT INPUT
        # =========================
        chat_input = st.chat_input("Întreabă-ți profesorul AI orice...")

     if chat_input:
    on_chat_submit(chat_input)
    # =========================
    # HISTORY (AFTER INPUT)
    # =========================
    for msg in st.session_state.history[-NUMBER_OF_MESSAGES_TO_DISPLAY:]:
        role = msg["role"]
        avatar = "👤" if role == "user" else "imgs/logo.jpg"

        with st.chat_message(role, avatar=avatar):
            st.write(msg["content"])
