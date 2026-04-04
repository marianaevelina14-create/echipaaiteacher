import streamlit as st
import logging
import time
import json
import requests
import base64
from PIL import Image, ImageEnhance
from datetime import datetime, timedelta
from openai import OpenAI, OpenAIError
from supabase import create_client

# ---------------- CONFIG ----------------
logging.basicConfig(level=logging.INFO)

OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY")
ASSISTANT_ID = st.secrets["OPENAI_ASSISTANT_ID"]

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- SAVE MESSAGE ----------------
def save_message(session_id, role, content):
    supabase.table("messages").insert({
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": datetime.utcnow().isoformat()
    }).execute()

# ---------------- BLOCK SYSTEM ----------------
def block_chat(session_id):
    blocked_until = datetime.utcnow() + timedelta(minutes=5)

    supabase.table("chat_limits").upsert({
        "session_id": session_id,
        "blocked_until": blocked_until.isoformat()
    }).execute()

def is_chat_blocked(session_id):
    res = supabase.table("chat_limits") \
        .select("*") \
        .eq("session_id", session_id) \
        .execute()

    if res.data:
        blocked_until = datetime.fromisoformat(res.data[0]["blocked_until"])
        return datetime.utcnow() < blocked_until

    return False

# ---------------- CHECKS ----------------
def is_inappropriate(text):
    bad_words = ["prost", "idiot", "stupid", "dracu"]
    return any(w in text.lower() for w in bad_words)

def is_apology(text):
    words = ["scuze", "imi pare rau", "îmi pare rău", "sorry", "mă ierți"]
    return any(w in text.lower() for w in words)

def is_educational(text):
    keywords = ["matematica", "istorie", "romana", "explica", "ajuta", "problema"]
    return any(k in text.lower() for k in keywords)

# ---------------- THREAD ----------------
def get_or_create_thread():
    if "thread_id" not in st.session_state or not st.session_state.thread_id:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
    return st.session_state.thread_id

# ---------------- SESSION INIT ----------------
def init_session():
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(time.time())

    if "history" not in st.session_state:
        st.session_state.history = []

    if "bad_count" not in st.session_state:
        st.session_state.bad_count = 0

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None

# ---------------- CHAT LOGIC ----------------
def on_chat_submit(chat_input, latest_updates):
    user_input = chat_input.strip()

    # BLOCK CHECK
    if is_chat_blocked(st.session_state.session_id):

        if is_apology(user_input) or is_educational(user_input):
            supabase.table("chat_limits") \
                .delete() \
                .eq("session_id", st.session_state.session_id) \
                .execute()

            st.session_state.bad_count = 0
            st.success("✅ Chat deblocat!")
            return

        st.warning("⛔ Chat blocat. Spune 'scuze' sau întreabă ceva educațional.")
        return

    # BAD WORDS
    if is_inappropriate(user_input):
        st.session_state.bad_count += 1

        if st.session_state.bad_count >= 3:
            block_chat(st.session_state.session_id)
            st.session_state.bad_count = 0
            st.error("⛔ Chat blocat 5 minute.")
            return

        st.warning(f"⚠️ Limbaj neadecvat ({st.session_state.bad_count}/3)")
        return

    # SAVE USER
    save_message(st.session_state.session_id, "user", user_input)

    try:
        assistant_reply = ""

        thread_id = get_or_create_thread()

        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_input
        )

        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID,
            tools=[{"type": "file_search"}]
        )

        messages = client.beta.threads.messages.list(
            thread_id=thread_id,
            order="desc",
            limit=10
        )

        for msg in messages.data:
            if msg.role == "assistant":
                assistant_reply = msg.content[0].text.value
                break

        # SAVE ASSISTANT
        save_message(st.session_state.session_id, "assistant", assistant_reply)

        st.session_state.history.append({"role": "user", "content": user_input})
        st.session_state.history.append({"role": "assistant", "content": assistant_reply})

    except Exception as e:
        st.error(str(e))

# ---------------- MAIN ----------------
def main():
    init_session()

    st.title("AI Teacher")

    chat_input = st.chat_input("Scrie mesajul tău...")
    if chat_input:
        on_chat_submit(chat_input, {})

    for msg in st.session_state.history[-20:]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

if __name__ == "__main__":
    main()
