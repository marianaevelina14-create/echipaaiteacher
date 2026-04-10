import streamlit as st
import time
import uuid
from openai import OpenAI

# =========================
# CONFIG
# =========================
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
ASSISTANT_ID = st.secrets["OPENAI_ASSISTANT_ID"]

# =========================
# "FIȘIER" CUVINTE NEADECVATE (SIMULARE)
# =========================
BAD_WORDS = [
    "prost", "idiot", "stupid", "dracu", "bou", "proasta"
]

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
# RULES
# =========================
def is_inappropriate(text):
    return any(word in text.lower() for word in BAD_WORDS)

def is_apology(text):
    text = text.lower().strip()
    return text in ["scuze", "îmi cer scuze", "imi cer scuze", "îmi pare rău", "imi pare rau"]

BLOCK_MESSAGE = "⛔ Chat blocat. Cereți scuze și revino la lecție."

UNBLOCK_MESSAGE = "🟢 Chat deblocat. Hai să revenim la lecție. Te pot ajuta doar pe baza documentului «Moara cu noroc»."

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

    # =========================
    # 🔴 DACA ESTE BLOCAT
    # =========================
    if st.session_state.chat_status == "blocked":
        st.error(BLOCK_MESSAGE)

        # DOAR SCUZE DEBLOCHEAZĂ
        if is_apology(user_input):
            st.session_state.chat_status = "active"
            st.session_state.bad_count = 0
            st.success(UNBLOCK_MESSAGE)
            st.rerun()

        return

    # =========================
    # 🔴 VERIFICARE LIMBAJ
    # =========================
    if is_inappropriate(user_input):
        st.session_state.bad_count += 1

        if st.session_state.bad_count >= 3:
            st.session_state.chat_status = "blocked"
            st.error(BLOCK_MESSAGE)
        else:
            st.warning(f"⚠️ Limbaj neadecvat ({st.session_state.bad_count}/3)")

        return

    # =========================
    # NORMAL CHAT
    # =========================
    st.session_state.history.append({"role": "user", "content": user_input})

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
            st.error("Eroare la OpenAI run")
            return

        if time.time() - start > 30:
            st.error("Timeout")
            return

        time.sleep(0.5)

    # RESPONSE
    messages = client.beta.threads.messages.list(
        thread_id=thread_id,
        order="desc",
        limit=10
    )

    reply = "Nu am primit răspuns."

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

    # =========================
    # STATUS BLOCKED / ACTIVE
    # =========================
    if st.session_state.chat_status == "blocked":
        st.error(BLOCK_MESSAGE)

        user_input = st.text_input("Scrie scuze pentru deblocare:")

        if user_input:
            if is_apology(user_input):
                st.session_state.chat_status = "active"
                st.session_state.bad_count = 0
                st.success(UNBLOCK_MESSAGE)
                st.rerun()
            else:
                st.error("❌ Nu este o scuză validă.")
        return

    else:
        st.success("🟢 Chat activ")

    # =========================
    # CHAT INPUT
    # =========================
    user_input = st.chat_input("Scrie mesajul tău...")

    if user_input:
        on_chat_submit(user_input)

    # =========================
    # HISTORY
    # =========================
    for msg in st.session_state.history[-20:]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()
