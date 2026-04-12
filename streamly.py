import streamlit as st
import logging
import time
from datetime import datetime
from openai import OpenAI
from supabase import create_client

logging.basicConfig(level=logging.INFO)

NUMBER_OF_MESSAGES_TO_DISPLAY = 20

OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", None)

if not OPENAI_API_KEY:
    st.error("Please add your OpenAI API key to the Streamlit secrets.toml file.")
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)
ASSISTANT_ID = st.secrets["OPENAI_ASSISTANT_ID"]

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# 🔥 LOGICĂ LIMBAJ
# =========================

def is_inappropriate(text):
    bad_words = ["prost", "idiot", "stupid", "dracu"]
    return any(word in text.lower() for word in bad_words)

def is_apology(text):
    return text.lower().strip() in [
        "scuze",
        "imi cer scuze",
        "imi pare rau"
    ]

# =========================
# SESSION
# =========================

def initialize_session_state():
    import uuid

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "history" not in st.session_state:
        st.session_state.history = []

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None

    # 🔥 CHEIA
    if "must_apologize" not in st.session_state:
        st.session_state.must_apologize = False

def get_or_create_thread():
    if not st.session_state.thread_id:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
    return st.session_state.thread_id

# =========================
# CHAT LOGIC
# =========================

def on_chat_submit(user_input):
    user_input = user_input.strip()

    # 🔒 dacă trebuie să-și ceară scuze
    if st.session_state.must_apologize:
        if is_apology(user_input):
            st.session_state.must_apologize = False
            st.success("🟢 Chat deblocat. Hai să revenim la lecție.")
            return
        else:
            st.error("⛔ Chat blocat. Cereți scuze și revino la lecție.")
            return

    # 🔥 dacă folosește limbaj neadecvat
    if is_inappropriate(user_input):
        st.session_state.must_apologize = True
        st.error("⛔ Chat blocat. Cereți scuze și revino la lecție.")
        return

    # =========================
    # NORMAL CHAT
    # =========================

    st.session_state.history.append({"role": "user", "content": user_input})

    try:
        thread_id = get_or_create_thread()

        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_input
        )

        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID
        )

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

# =========================
# UI
# =========================

def render_sidebar():
    st.sidebar.title("AI Teacher")
    st.sidebar.write("Asistent educațional AI")
    st.sidebar.write("Română")

def main():
    initialize_session_state()
    render_sidebar()

    st.markdown("## Chat")

    # 🔥 CHAT INPUT SIMPLU
    chat_input = st.chat_input("Întreabă-ți profesorul AI orice...")

    if chat_input:
        on_chat_submit(chat_input)

    # =========================
    # HISTORY
    # =========================
    for message in st.session_state.history[-NUMBER_OF_MESSAGES_TO_DISPLAY:]:
        role = message["role"]
        avatar = "👤" if role == "user" else "🤖"

        with st.chat_message(role, avatar=avatar):
            st.write(message["content"])

# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()
