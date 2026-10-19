
import requests
import streamlit as st
from google import genai
from google.genai import types

from prompts import (
    SYSTEM_PROMPT,
    WELCOME_PROMPT,
    SUMMARY_REQUEST_PROMPT,
)

# ==========================================
# CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="MacroSnap",
    page_icon="🥗",
    layout="wide",
)

gemini_api_key = st.secrets["gemini_api_key"]
telegram_bot_token = st.secrets["telegram_bot_token"]
telegram_chat_id = str(st.secrets["telegram_chat_id"])

MODEL_NAME = "gemini-3.8-flash"
TELEGRAM_MESSAGE_LIMIT = 4000


@st.cache_resource
def get_gemini_client(api_key):
    return genai.Client(api_key=api_key)


gemini_client = get_gemini_client(gemini_api_key)


# ==========================================
# TELEGRAM FUNCTIONS
# ==========================================

def send_telegram_summary(user_name, summary):
    """Send a nutrition summary to the configured Telegram chat."""
    if not summary or not summary.strip():
        return False, "The summary is empty."

    message_text = (
        f"🥗 MacroSnap Nutrition Summary\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 Name: {user_name}\n\n"
        f"{summary.strip()}"
    )

    # Telegram text messages have a 4096-character limit.
    if len(message_text) > TELEGRAM_MESSAGE_LIMIT:
        message_text = (
            message_text[: TELEGRAM_MESSAGE_LIMIT - 25]
            + "\n\n[Summary shortened]"
        )

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage",
            json={
                "chat_id": telegram_chat_id,
                "text": message_text,
            },
            timeout=20,
        )

        try:
            result = response.json()
        except ValueError:
            return False, f"Telegram returned an unexpected response (HTTP {response.status_code})."

        if response.ok and result.get("ok"):
            message_id = result.get("result", {}).get("message_id")
            return True, f"Telegram message ID: {message_id}"

        description = result.get(
            "description",
            f"Telegram returned HTTP {response.status_code}",
        )
        return False, description

    except requests.RequestException as error:
        return False, f"Could not connect to Telegram: {error}"


# ==========================================
# CHAT FUNCTIONS
# ==========================================

def render_messages(message):
    with st.chat_message(message["role"]):
        if message["kind"] == "text":
            st.write(message["content"])
        elif message["kind"] == "image":
            st.image(message["content"])


def add_message(role, kind, content):
    message = {
        "role": role,
        "kind": kind,
        "content": content,
    }
    st.session_state.messages.append(message)
    render_messages(message)


def ask_gemini(parts):
    try:
        response = st.session_state.chat.send_message(parts)
        return response.text or "Sorry, I couldn't generate a response."
    except Exception as error:
        return f"Sorry, something went wrong: {error}"


# ==========================================
# ONBOARDING
# ==========================================

if "onboarded" not in st.session_state:
    st.session_state.onboarded = False

if not st.session_state.onboarded:
    st.title("MacroSnap 🥗")
    st.caption("Snap it. Track it. Share it on Telegram.")

    with st.form("onboarding_form"):
        name = st.text_input("Enter your name:")
        submitted = st.form_submit_button("Let's Get Started!")

    if submitted:
        if not name.strip():
            st.warning("Please enter your name.")
        else:
            st.session_state.name = name.strip()
            st.session_state.onboarded = True
            st.rerun()

    st.stop()


# ==========================================
# INITIALIZE GEMINI CHAT
# ==========================================

if "chat" not in st.session_state:
    st.session_state.chat = gemini_client.chats.create(
        model=MODEL_NAME,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
        ),
    )


# ==========================================
# INITIALIZE MESSAGE HISTORY
# ==========================================

if "messages" not in st.session_state:
    welcome_message = WELCOME_PROMPT.format(
        name=st.session_state.name
    )

    st.session_state.messages = [
        {
            "role": "assistant",
            "kind": "text",
            "content": welcome_message,
        }
    ]


# ==========================================
# MAIN INTERFACE
# ==========================================

header_col, button_col = st.columns(
    [5, 2],
    vertical_alignment="center",
)

with header_col:
    st.title("MacroSnap 🥗")
    st.caption("Snap it. Track it. Share it on Telegram.")

with button_col:
    if st.button(
        "📲 Send Summary to Telegram",
        use_container_width=True,
    ):
        if len(st.session_state.messages) <= 1:
            st.warning(
                "Please chat with MacroSnap or analyze a meal "
                "before generating a summary."
            )
        else:
            with st.spinner("Generating your nutrition summary..."):
                summary = ask_gemini([SUMMARY_REQUEST_PROMPT])

            if (
                not summary
                or summary.startswith("Sorry, something went wrong:")
            ):
                st.error(summary or "Could not generate the summary.")
            else:
                with st.spinner("Sending summary to Telegram..."):
                    success, info = send_telegram_summary(
                        st.session_state.name,
                        summary,
                    )

                if success:
                    st.success("Nutrition summary sent to Telegram!")
                    st.caption(info)
                else:
                    st.error(f"Failed to send Telegram summary: {info}")


st.caption(
    f"Logged in as {st.session_state.name} | "
    f"Telegram: connected to your configured chat"
)

# Display existing messages exactly once.
for message in st.session_state.messages:
    render_messages(message)


# ==========================================
# CHAT INPUT: TEXT + MEAL PHOTO
# ==========================================

user_input = st.chat_input(
    "Ask a question, or attach a photo of your meal",
    accept_file=True,
    file_type=["jpg", "jpeg", "png"],
)

if user_input:
    photo = user_input.files[0] if user_input.files else None
    text = user_input.text
    parts = []

    if photo is not None:
        photo_bytes = photo.getvalue()
        add_message("user", "image", photo_bytes)

        parts.append(
            types.Part.from_bytes(
                data=photo_bytes,
                mime_type=photo.type,
            )
        )

    if text:
        add_message("user", "text", text)
        parts.append(text)
    elif photo is not None:
        parts.append(
            "What is this meal? Please analyze it and provide "
            "nutritional information, including estimated calories, "
            "protein, carbohydrates, and fat where possible."
        )

    if parts:
        with st.spinner("Analyzing your meal..."):
            answer = ask_gemini(parts)

        add_message("assistant", "text", answer)
