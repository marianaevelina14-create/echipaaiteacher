import streamlit as st
import time
import uuid
from openai import OpenAI

# =========================
# CONFIG
# =========================
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
ASSISTANT_ID = st.secrets["OPENAI_ASSISTANT_ID"]

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# SESSION STATE
# =========================
def init_session():
    if "chat_status" not in st.session_state:
        st.session_state.chat_status = "active"

    if "bad_count" not in st.session_state:
        st.session_state.bad_count = 0

    if "history" not in st.session_state:
        st.session_state.history = []

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

# =========================
# SIMPLE CHECKS
# =========================
def is_apology(text):
    return text.lower().strip() in ["scuze", "îmi cer scuze", "imi cer scuze", "imi pare rau"]

def is_inappropriate(text):
    bad_words = ["prost", "idiot", "stupid", "dracu"]
    return any(w in text.lower() for w in bad_words)

# =========================
# OPENAI THREAD
# =========================
def get_thread():
    if not st.session_state.thread_id:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
    return st.session_state.thread_id

# =========================
# CHAT LOGIC
# =========================
def on_chat_submit(user_input):
    user_input = user_input.strip()

    # BLOCKED STATE
    if st.session_state.chat_status == "blocked":
        st.error("⛔ Chat blocat. Scrie o scuză pentru deblocare.")
        return

    # BAD LANGUAGE
    if is_inappropriate(user_input):
        st.session_state.bad_count += 1

        if st.session_state.bad_count >= 3:
            st.session_state.chat_status = "blocked"
            st.error("⛔ Ai fost blocat pentru limbaj nepotrivit.")
        else:
            st.warning(f"⚠️ Limbaj nepotrivit ({st.session_state.bad_count}/3)")
        return

    # SAVE USER MESSAGE
    st.session_state.history.append({"role": "user", "content": user_input})

    # SEND TO OPENAI
    thread_id = get_thread()

    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_input
    )

    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=ASSISTANT_ID
    )

    # WAIT LOOP
    start = time.time()
    while True:
        status = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )

        if status.status == "completed":
            break

        if status.status in ["failed", "cancelled", "expired"]:
            st.error("Run failed")
            return

        if time.time() - start > 30:
            st.error("Timeout")
            return

        time.sleep(0.5)

    # GET RESPONSE
    messages = client.beta.threads.messages.list(
        thread_id=thread_id,
        order="desc",
        limit=10
    )

    reply = "No response."

    for m in messages.data:
        if m.role == "assistant":
            reply = m.content[0].text.value
            break

    st.session_state.history.append({"role": "assistant", "content": reply})

# =========================
# UI
# =========================
def main():
    st.set_page_config(page_title="AI Teacher", page_icon="🎓")

    init_session()

    st.title("🎓 AI Teacher")

    # STATUS
    if st.session_state.chat_status == "active":
        st.success("🟢 Chat activ")
    else:
        st.error("⛔ Chat blocat")

        apology = st.text_input("Scrie scuze pentru deblocare:")

        if apology:
            if is_apology(apology):
                st.session_state.chat_status = "active"
                st.session_state.bad_count = 0
                st.success("Deblocat!")
                st.rerun()
            else:
                st.error("Scuză invalidă")
        return

    # CHAT INPUT
    user_input = st.chat_input("Scrie mesajul tău...")

    if user_input:
        on_chat_submit(user_input)

    # HISTORY
    for msg in st.session_state.history[-20:]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()
