

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


def save_message(session_id, role, content):
    supabase.table("messages").insert({
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": datetime.utcnow().isoformat()
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
def initialize_session_state():
    if "session_id" not in st.session_state:
        sid = st.query_params.get("session_id")

        if not sid:
            sid = str(uuid.uuid4())
            st.query_params.update({"session_id": sid})

        st.session_state.session_id = sid

    if "history" not in st.session_state:
        st.session_state.history = []

    if "bad_count" not in st.session_state:
        st.session_state.bad_count = 0

    if "chat_status" not in st.session_state:
        st.session_state.chat_status = "active"

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
 # ✅ ADĂUGĂ ASTA
    if "blocked_until" not in st.session_state:
        st.session_state.blocked_until = None
def render_sidebar():
    st.sidebar.title("AI Teacher")
    st.sidebar.write("Asistent educațional AI")

    st.sidebar.markdown("### Materii")
    st.sidebar.write("Română")
    

# =========================
# MAIN
# =========================
def main():
    """
    Display Streamlit updates and handle the chat interface.
    """
    initialize_session_state()
    render_sidebar()

    # load history
    if not st.session_state.history:
        st.session_state.history = [
            {"role": m["role"], "content": m["content"]}
            for m in load_messages(st.session_state.session_id)
        ]

    # block check
  if is_hard_blocked(st.session_state.session_id):
        st.warning("⛔ Chat blocat")

        apology = st.text_input("Scrie scuze:")

    elif st.session_state.chat_status == "active":
        st.success("🟢 Chat activ")

    if not st.session_state.history and not st.session_state.conversation_history:
        st.session_state.conversation_history = initialize_conversation()

    # Apply custom CSS for the updated AI Teacher design (Blue/Orange theme based on the logo)
    st.markdown(
        """
        <style>
        /* Main background and overall text */
        [data-testid="stAppViewContainer"] {
            background-color: #f0f6fc; /* Light blue main background */
        }
        
        [data-testid="stHeader"] {
            background-color: transparent !important;
        }

        /* Make all chat message bubbles completely transparent */
        [data-testid="stChatMessage"] {
            background-color: transparent !important; 
            border: none !important;
            border-radius: 0;
            padding: 0.5rem 0;
            margin-bottom: 0.8rem;
            box-shadow: none !important;
        }
        [data-testid="stChatMessage"] > div,
        [data-testid="stChatMessageContent"] {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }
        
        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background-color: #1b3a97; /* Royal/Navy Blue exactly as in the image */
            color: #ffffff;
        }
        [data-testid="stSidebar"] * {
            color: #ffffff;
        }
        
        /* Headings in sidebar */
        .sidebar-heading {
            color: #ff7f00; /* Vibrant Orange accents */
            font-weight: bold;
            font-size: 1rem;
            margin-top: 1rem;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        /* Features list */
        .feature-item {
            margin-bottom: 0.3rem;
            font-size: 0.9rem;
            line-height: 1.3;
        }
        .feature-item span {
            color: #ff7f00; /* Vibrant Orange bullets */
            margin-right: 8px;
            font-weight: bold;
            font-size: 1.3rem; /* Make the dot stand out */
            line-height: 0;
        }
        
        /* Subject pills */
        .subject-container {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 5px;
        }
        .subject-pill {
            display: inline-flex;
            align-items: center;
            background-color: rgba(255, 255, 255, 0.15);
            border: 1px solid rgba(255, 255, 255, 0.6); /* White accent border for contrast against blue */
            border-radius: 15px;
            padding: 4px 10px;
            font-size: 0.8rem;
            color: white;
            transition: background-color 0.2s;
        }
        
        /* Chat message text color to be black */
        [data-testid="stChatMessageContent"] * {
            color: #000000 !important; /* Black text */
        }
        .subject-pill:hover {
            background-color: rgba(255, 255, 255, 0.3);
        }
        .subject-pill span {
            margin-right: 6px;
        }
        
        /* Refined primary button (Clear Chat) */
        [data-testid="stBaseButton-secondary"] {
            background-color: transparent !important;
            color: #6b7280 !important;
            border: 1px solid #d1d5db !important;
            font-weight: 600;
            border-radius: 8px !important;
            padding: 0.4rem 1.2rem !important;
            box-shadow: none !important;
            transition: all 0.2s ease;
        }
        [data-testid="stBaseButton-secondary"]:hover {
            background-color: #f3f4f6 !important;
            border-color: #9ca3af !important;
            color: #374151 !important;
            transform: translateY(-1px);
        }
        
        /* Chat header and UI improvements */
        .chat-header {
            font-size: 2.2rem;
            font-weight: 800;
            color: #ff7f00 !important; /* Orange Header */
            margin: 0;
            padding-bottom: 0;
        }
        
        div[data-testid="stHorizontalBlock"] {
    background-color: #000000 !important;
    padding: 1.5rem !important;
    border-radius: 12px;
}
  st.markdown("""
<style>
div[data-testid="stHorizontalBlock"] {
    background-color: #000000 !important;
    padding: 12px 16px !important;
    border-radius: 10px !important;
}
</style>
""", unsafe_allow_html=True)
        /* Antet (Header) background white */
        [data-testid="stHorizontalBlock"] {
            background-color: #ffffff !important;
            padding: 2rem 5rem !important;
            margin: -6rem -5rem 2rem -5rem !important; /* Extindem pt efect full-width vizual */
            border-bottom: 1px solid #e5e7eb !important;
            border-radius: 0 !important;
            align-items: center !important;
            box-shadow: none !important;
            width: calc(100% + 10rem) !important;
            max-width: none !important;
        }
        
        /* Send Button Styling */
        [data-testid="stChatInputSubmitButton"] {
            background-color: #ff7f00 !important;
            border-radius: 50% !important; /* Circular button */
            width: 35px !important;
            height: 35px !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin-right: 5px;
            border: none !important;
            box-shadow: 0 2px 4px rgba(255,127,0,0.3);
        }
        [data-testid="stChatInputSubmitButton"] svg {
            fill: #ffffff !important;
            color: #ffffff !important;
            width: 18px !important;
            height: 18px !important;
        }

        /* Bara de search (Chat Input) alba */
        [data-testid="stChatInput"] {
            background-color: transparent !important;
        }
        [data-testid="stChatInput"] > div {
            background-color: #ffffff !important;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            padding: 2px !important;
        }
        [data-testid="stChatInput"] textarea {
            background-color: #ffffff !important;
            color: #000000 !important;
            border: none !important;
        }
        /* Asiguram background alb la focus */
        [data-testid="stChatInput"] textarea:focus {
            background-color: #ffffff !important;
            outline: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Sidebar Content
    img_path = "imgs/logo.jpg"
    img_base64 = img_to_base64(img_path)
    if img_base64:
        st.sidebar.markdown(
            f'<div style="display:flex; align-items:center; gap:20px; margin-top: -30px; margin-bottom: 15px;">'
            f'<div style="background-color:white; padding:5px; height: 60px; width: 60px; display:flex; align-items:center; justify-content:center; border-radius: 12px;">'
            f'<img src="data:image/jpeg;base64,{img_base64}" style="width: 50px;">'
            f'</div>'
            f'<h1 style="margin:0; color:#ff7f00; font-size: 1.6rem; font-weight: bold;">AI Teacher</h1>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown("<h1 style='color:#ff7f00; font-size: 2rem;'>AI Teacher</h1>", unsafe_allow_html=True)
    
    # (Removed the explicit <hr> line separating logo and ABOUT text so it perfectly matches the image)
    
    st.sidebar.markdown("<div class='sidebar-heading'>DESPRE</div>", unsafe_allow_html=True)
    st.sidebar.markdown("""
    <div style='font-size: 0.9rem; line-height: 1.4; color: white;'>
    Un asistent educațional inteligent, creat pentru a te ajuta să înveți la o varietate de materii, inclusiv Matematică, Istorie și Limba Română.
    </div>
    """, unsafe_allow_html=True)
    /* 🔝 HEADER NEGRU (bara de sus Streamlit) */
[data-testid="stHeader"] {
    background-color: #000000 !important;
    color: white !important;
}

[data-testid="stHeader"] * {
    color: white !important;
}
    
    st.sidebar.markdown("<div class='sidebar-heading'>FUNCȚIONALITĂȚI</div>", unsafe_allow_html=True)
    st.sidebar.markdown("""
    <div class='feature-item'><span>.</span>Învățare interactivă prin conversații</div>
    <div class='feature-item'><span>.</span>Tutorat personalizat pe materii</div>
    <div class='feature-item'><span>.</span>Explicații pas cu pas</div>
    <div class='feature-item'><span>.</span>Suport educațional 24/7</div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("<div class='sidebar-heading'>CUM FUNCȚIONEAZĂ</div>", unsafe_allow_html=True)
    st.sidebar.markdown("""
    <div style='font-size: 0.9rem; line-height: 1.4; color: white;'>
    Scrie întrebarea ta în chat-ul de mai jos și primește răspunsuri instantanee și personalizate. Poți întreba despre orice subiect, poți cere detalii sau poți solicita ajutor la teme.
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown("<div class='sidebar-heading'>MATERII DISPONIBILE</div>", unsafe_allow_html=True)
    st.sidebar.markdown("""
    <div class='subject-container'>
        <div class='subject-pill'><span>📐</span> Matematică</div>
        <div class='subject-pill'><span>📜</span> Istorie</div>
        <div class='subject-pill'><span>🇷🇴</span> Română</div>
        <div class='subject-pill'><span>🔬</span> Științe</div>
        <div class='subject-pill'><span>💻</span> Programare</div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("<div style='border-top: 1px solid rgba(255,255,255,0.1); padding-top: 1rem; margin-top: 1rem; text-align: center; color: white; font-size: 0.85rem;'>Susținut de Inteligența Artificială</div>", unsafe_allow_html=True)

    # Main Chat Area
    st.write("") # small padding
    col1, col2 = st.columns([5, 1])
    with col1:
        st.markdown("<h2 class='chat-header'>Chat</h2>", unsafe_allow_html=True)
    with col2:
        if st.button("💡 Cere Hint"):
            hint_message = "Mă poți ajuta cu un mic indiciu pentru a continua? Te rog nu-mi da rezolvarea completă."
            latest_updates = load_streamlit_updates()
            with st.spinner("Pregătesc indiciul..."):
                on_chat_submit(hint_message, latest_updates)

    # Chat Input Processing
    chat_input = st.chat_input("Întreabă-ți profesorul AI orice...")
    if chat_input:
        latest_updates = load_streamlit_updates()
        on_chat_submit(chat_input, latest_updates)
   # 🔒 verificăm dacă chat-ul este blocat
blocked = is_chat_blocked(st.session_state.session_id)

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
            st.success("Deblocat!")
            st.rerun()
        return

    # chat input
   user_input = None

if not is_hard_blocked(st.session_state.session_id):
    user_input = st.chat_input("Scrie mesaj...")

    if user_input:
        on_chat_submit(user_input)

    # history
    for msg in st.session_state.history[-NUMBER_OF_MESSAGES_TO_DISPLAY:]:
        avatar = "👤" if msg["role"] == "user" else "imgs/logo.jpg"

        with st.chat_message(msg["role"], avatar=avatar):
            st.write(msg["content"])


# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    main()
