import sys
import json
import urllib.request
import html

if len(sys.argv) < 2:
    print("Usage: python send_telegram_message.py 'Message text'")
    exit(1)

text = sys.argv[1]

# Read token and chat ID from .env
telegram_token = None
telegram_chat_id = None
env_path = "./.env"

try:
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                telegram_token = line.split("=", 1)[1].strip()
            elif line.startswith("TELEGRAM_CHAT_ID="):
                telegram_chat_id = line.split("=", 1)[1].strip()
except Exception as e:
    print(f"Error reading .env: {e}")
    exit(1)

if not telegram_token or not telegram_chat_id:
    print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured in .env")
    exit(1)

url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
payload = {
    "chat_id": telegram_chat_id,
    "text": text,
    "parse_mode": "HTML",
    "disable_web_page_preview": True
}
headers = {
    "Content-Type": "application/json; charset=utf-8"
}

req = urllib.request.Request(
    url, 
    data=json.dumps(payload).encode("utf-8"), 
    headers=headers,
    method="POST"
)
try:
    with urllib.request.urlopen(req) as res:
        resp = json.loads(res.read().decode("utf-8"))
        if not resp.get("ok"):
            print(f"Error sending message: {resp.get('description')}")
        else:
            print("Message sent successfully.")
except Exception as e:
    print(f"Exception sending message: {e}")
    exit(1)
