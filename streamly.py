
import streamlit as st
import logging
from PIL import Image, ImageEnhance
import time
import json
import requests
import base64
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
from datetime import datetime, timedelta

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



def is_chat_blocked(session_id):
    response = supabase.table("chat_limits") \
        .select("*") \
        .eq("session_id", session_id) \
        .execute()

    if response.data:
        blocked_until = response.data[0]["blocked_until"]
        blocked_until = datetime.fromisoformat(blocked_until)

        if datetime.utcnow() < blocked_until:
            return True

    return False


def is_inappropriate(text):
    bad_words = ["prost", "idiot", "stupid", "dracu"]

    for word in bad_words:
        if word in text.lower():
            return True
    return False


def is_apology(text):
    apologies = [
        "scuze",
        "imi pare rau",
        "îmi pare rău",
        "sorry",
        "ma ierti",
        "mă ierți"
    ]
    return any(word in text.lower() for word in apologies)
    supabase.table("messages").insert({
        "session_id": session_id,
        "role": role,
        "content": content
    }).execute()
    from datetime import datetime, timedelta

def block_chat(session_id):
    blocked_until = datetime.utcnow() + timedelta(minutes=5)

    supabase.table("chat_limits").upsert({
        "session_id": session_id,
        "blocked_until": blocked_until.isoformat()
    }).execute()


def is_chat_blocked(session_id):
    response = supabase.table("chat_limits") \
        .select("*") \
        .eq("session_id", session_id) \
        .execute()

    if response.data:
        blocked_until = response.data[0]["blocked_until"]
        blocked_until = datetime.fromisoformat(blocked_until)

        if datetime.utcnow() < blocked_until:
            return True

    return False


def is_inappropriate(text):
    bad_words = ["prost", "idiot", "stupid", "dracu"]

    for word in bad_words:
        if word in text.lower():
            return True
    return False
# Streamlit Page Configuration
def is_educational(text):
    keywords = ["matematica", "istorie", "romana", "explica", "ajuta", "problema"]
    return any(k in text.lower() for k in keywords)
st.set_page_config(
    page_title="AI Teacher Web App",
    page_icon="imgs/logo.jpg",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": "https://github.com/AdieLaine/Streamly",
        "Report a bug": "https://github.com/AdieLaine/Streamly",
        "About": "AI Teacher Web App"
    }
)
import uuid

# =========================
# SESSION ID (PERSISTENT)
# =========================
if "session_id" not in st.session_state:
    st.session_state.session_id = st.query_params.get("session_id", None)

if not st.session_state.session_id:
    st.session_state.session_id = str(uuid.uuid4())
    st.query_params["session_id"] = st.session_state.session_id


# =========================
# SESSION STATE INIT
# =========================
if "history" not in st.session_state:
    st.session_state.history = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

if "bad_count" not in st.session_state:
    st.session_state.bad_count = 0

if "warning_stage" not in st.session_state:
    st.session_state.warning_stage = 0

if "chat_status" not in st.session_state:
    st.session_state.chat_status = "active"
   

@st.cache_data(show_spinner=False)
def img_to_base64(image_path):
    """Convert image to base64."""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        logging.error(f"Error converting image to base64: {str(e)}")
        return None

@st.cache_data(show_spinner=False)
def long_running_task(duration):
    """
    Simulates a long-running operation.

    Parameters:
    - duration: int, duration of the task in seconds

    Returns:
    - str: Completion message
    """
    time.sleep(duration)
    return "Long-running operation completed."

@st.cache_data(show_spinner=False)
def load_and_enhance_image(image_path, enhance=False):
    """
    Load and optionally enhance an image.

    Parameters:
    - image_path: str, path of the image
    - enhance: bool, whether to enhance the image or not

    Returns:
    - img: PIL.Image.Image, (enhanced) image
    """
    img = Image.open(image_path)
    if enhance:
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.8)
    return img

@st.cache_data(show_spinner=False)
def load_streamlit_updates():
    """Load the latest Streamlit updates from a local JSON file."""
    try:
        with open("data/streamlit_updates.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading JSON: {str(e)}")
        return {}

def get_streamlit_api_code_version():
    """
    Get the current Streamlit API code version from the Streamlit API documentation.

    Returns:
    - str: The current Streamlit API code version.
    """
    try:
        response = requests.get(API_DOCS_URL)
        if response.status_code == 200:
            return "1.36"
    except requests.exceptions.RequestException as e:
        logging.error(f"Error connecting to the Streamlit API documentation: {str(e)}")
    return None

def display_streamlit_updates():
    """Display the latest updates of the Streamlit."""
    with st.expander("Streamlit 1.36 Announcement", expanded=False):
        st.markdown("For more details on this version, check out the [Streamlit Forum post](https://docs.streamlit.io/library/changelog#version).")

def initialize_conversation():
    """
    Initialize the conversation history with system and assistant messages.

    Returns:
    - list: Initialized conversation history.
    """
    conversation_history = [
        {"role": "system", "content": "You are AI Teacher, a specialized AI educational assistant."},
        {"role": "system", "content": "You are powered by the OpenAI GPT-4o-mini model."},
        {"role": "system", "content": "Refer to conversation history to provide context to your response."}
    ]
    return conversation_history

@st.cache_data(show_spinner=False)
def get_latest_update_from_json(keyword, latest_updates):
    """
    Fetch the latest Streamlit update based on a keyword.

    Parameters:
    - keyword (str): The keyword to search for in the Streamlit updates.
    - latest_updates (dict): The latest Streamlit updates data.

    Returns:
    - str: The latest update related to the keyword, or a message if no update is found.
    """
    for section in ["Highlights", "Notable Changes", "Other Changes"]:
        for sub_key, sub_value in latest_updates.get(section, {}).items():
            for key, value in sub_value.items():
                if keyword.lower() in key.lower() or keyword.lower() in value.lower():
                    return f"Section: {section}\nSub-Category: {sub_key}\n{key}: {value}"
    return "No updates found for the specified keyword."
def get_or_create_thread():
    if not st.session_state.thread_id:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
    return st.session_state.thread_id

def construct_formatted_message(latest_updates):
    """
    Construct formatted message for the latest updates.

    Parameters:
    - latest_updates (dict): The latest Streamlit updates data.

    Returns:
    - str: Formatted update messages.
    """
    formatted_message = []
    highlights = latest_updates.get("Highlights", {})
    version_info = highlights.get("Version 1.36", {})
    if version_info:
        description = version_info.get("Description", "No description available.")
        formatted_message.append(f"- **Version 1.36**: {description}")

    for category, updates in latest_updates.items():
        formatted_message.append(f"**{category}**:")
        for sub_key, sub_values in updates.items():
            if sub_key != "Version 1.36":  # Skip the version info as it's already included
                description = sub_values.get("Description", "No description available.")
                documentation = sub_values.get("Documentation", "No documentation available.")
                formatted_message.append(f"- **{sub_key}**: {description}")
                formatted_message.append(f"  - **Documentation**: {documentation}")
    return "\n".join(formatted_message)

@st.cache_data(show_spinner=False)
def get_latest_update_from_json(keyword, latest_updates):
    for section in ["Highlights", "Notable Changes", "Other Changes"]:
        for sub_key, sub_value in latest_updates.get(section, {}).items():
            for key, value in sub_value.items():
                if keyword.lower() in key.lower() or keyword.lower() in value.lower():
                    return f"Section: {section}\nSub-Category: {sub_key}\n{key}: {value}"
    return "No updates found for the specified keyword."



 def on_chat_submit(chat_input, latest_updates):
    user_input = chat_input.strip()

    # =========================
    # 1. BLOCK CHECK
    # =========================
    if is_chat_blocked(st.session_state.session_id):

        if is_apology(user_input):
            supabase.table("chat_limits") \
                .delete() \
                .eq("session_id", st.session_state.session_id) \
                .execute()

            st.session_state.chat_status = "active"
            st.session_state.bad_count = 0
            st.session_state.warning_stage = 0

            st.success("🟢 Chat deblocat!")
            return

        st.warning("⛔ Chat blocat. Cereți scuze pentru a continua.")
        return

    # =========================
    # 2. BAD WORD CHECK
    # =========================
    if is_inappropriate(user_input):

        st.session_state.bad_count += 1
        st.session_state.warning_stage = st.session_state.bad_count

        if st.session_state.bad_count < 3:
            st.warning("⚠️ Limbaj neadecvat. Te rog să respecți regulile.")
            return

        block_chat(st.session_state.session_id)
        st.session_state.chat_status = "blocked"

        st.error("⛔ Chat blocat. Cereți scuze pentru a continua.")
        return

    # =========================
    # 3. SAVE USER MESSAGE
    # =========================
    save_message(st.session_state.session_id, "user", user_input)

    try:
        thread_id = get_or_create_thread()

        # send message
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_input
        )

        # run assistant (SAFE VERSION)
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID
        )

        # wait until run completes
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )

            if run_status.status == "completed":
                break

            if run_status.status == "failed":
                st.error("Run failed.")
                return

            time.sleep(0.5)

        # get messages
        messages = client.beta.threads.messages.list(
            thread_id=thread_id,
            order="desc",
            limit=10
        )

        assistant_reply = "Nu am primit răspuns."

        for msg in messages.data:
            if msg.role == "assistant":
                parts = [
                    c.text.value for c in msg.content
                    if c.type == "text"
                ]
                if parts:
                    assistant_reply = "\n".join(parts)
                    break

        # =========================
        # 5. SAVE ASSISTANT MESSAGE
        # =========================
        save_message(st.session_state.session_id, "assistant", assistant_reply)

        # =========================
        # 6. UPDATE UI HISTORY
        # =========================
        st.session_state.history.append({"role": "user", "content": user_input})
        st.session_state.history.append({"role": "assistant", "content": assistant_reply})

    except Exception as e:
        st.error(f"Eroare: {str(e)}")def initialize_session_state():
    if "warning_stage" not in st.session_state:
        st.session_state.warning_stage = 0

    if "chat_status" not in st.session_state:
        st.session_state.chat_status = "active"

    # SESSION ID (SAFE VERSION)
    session_id = st.query_params.get("session_id")

    if not session_id:
        session_id = str(uuid.uuid4())
        st.query_params.update({"session_id": session_id})

    st.session_state.session_id = session_id

    # HISTORY
    if "history" not in st.session_state:
        st.session_state.history = []

    # THREAD
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None

    # BAD WORD COUNTER
    if "bad_count" not in st.session_state:
        st.session_state.bad_count = 0

    # OPTIONAL (îți lipsește dar îl folosești mai jos în cod)
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []
    import streamlit as st
import logging
import time
import json
import requests
import base64
import uuid
from datetime import datetime, timedelta
from openai import OpenAI
from supabase import create_client
from PIL import Image, ImageEnhance

# =========================
# CONFIG
# =========================
logging.basicConfig(level=logging.INFO)

NUMBER_OF_MESSAGES_TO_DISPLAY = 20
API_DOCS_URL = "https://docs.streamlit.io/library/api-reference"

OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
ASSISTANT_ID = st.secrets["OPENAI_ASSISTANT_ID"]

client = OpenAI(api_key=OPENAI_API_KEY)

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

# =========================
# STREAMLIT CONFIG
# =========================
st.set_page_config(
    page_title="AI Teacher",
    page_icon="imgs/logo.jpg",
    layout="wide"
)

# =========================
# CSS (SEPARAT)
# =========================
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background-color: #f0f6fc;
}

[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
}

[data-testid="stChatMessageContent"] * {
    color: #000 !important;
}

[data-testid="stSidebar"] {
    background-color: #1b3a97;
    color: white;
}

</style>
""", unsafe_allow_html=True)

# =========================
# HELPERS
# =========================
def is_apology(text):
    words = ["scuze", "imi pare rau", "îmi pare rău", "sorry"]
    return any(w in text.lower() for w in words)


def is_inappropriate(text):
    bad = ["prost", "idiot", "stupid", "dracu"]
    return any(w in text.lower() for w in bad)


def is_chat_blocked(session_id):
    response = supabase.table("chat_limits") \
        .select("*") \
        .eq("session_id", session_id) \
        .execute()

    if response.data:
        blocked_until = datetime.fromisoformat(response.data[0]["blocked_until"])
        return datetime.utcnow() < blocked_until

    return False


def block_chat(session_id):
    supabase.table("chat_limits").upsert({
        "session_id": session_id,
        "blocked_until": (datetime.utcnow() + timedelta(minutes=5)).isoformat()
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
    if "thread_id" not in st.session_state or not st.session_state.thread_id:
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
            st.query_params["session_id"] = sid
        st.session_state.session_id = sid

    if "history" not in st.session_state:
        st.session_state.history = []

    if "bad_count" not in st.session_state:
        st.session_state.bad_count = 0

    if "chat_status" not in st.session_state:
        st.session_state.chat_status = "active"

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None


# =========================
# CHAT LOGIC
# =========================
def on_chat_submit(user_input):

    if is_chat_blocked(st.session_state.session_id):
        st.warning("⛔ Chat blocat")
        return

    if is_inappropriate(user_input):
        st.session_state.bad_count += 1

        if st.session_state.bad_count >= 3:
            block_chat(st.session_state.session_id)
            st.error("⛔ Chat blocat 5 min")
            return

        st.warning("⚠️ Limbaj neadecvat")
        return

    save_message(st.session_state.session_id, "user", user_input)

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
        status = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )

        if status.status == "completed":
            break

        time.sleep(0.5)

    messages = client.beta.threads.messages.list(
        thread_id=thread_id,
        order="desc",
        limit=5
    )

    reply = "No response"

    for m in messages.data:
        if m.role == "assistant":
            reply = "\n".join([c.text.value for c in m.content if c.type == "text"])
            break

    save_message(st.session_state.session_id, "assistant", reply)

    st.session_state.history.append({"role": "user", "content": user_input})
    st.session_state.history.append({"role": "assistant", "content": reply})


# =========================
# SIDEBAR
# =========================
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

    st.title("Chat AI Teacher")

    # load history
    if not st.session_state.history:
        st.session_state.history = [
            {"role": m["role"], "content": m["content"]}
            for m in load_messages(st.session_state.session_id)
        ]

    # block check
    if is_chat_blocked(st.session_state.session_id):
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
