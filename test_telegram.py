
import streamlit as st
import requests

token = st.secrets["telegram_bot_token"]
chat_id = st.secrets["telegram_chat_id"]

response = requests.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    json={
        "chat_id": chat_id,
        "text": "🥗 Hello! MacroSnap Telegram integration is working!",
    },
    timeout=20,
)

result = response.json()
print(result)

if result.get("ok"):
    print("SUCCESS: Telegram message sent!")
else:
    print("FAILED:", result)
