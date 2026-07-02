import os
import json
import urllib.request
import urllib.parse
import datetime
import html

# Read token and chat ID from environment variables or fallback to .env
telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")

if not telegram_token or not telegram_chat_id:
    if os.path.exists(".env"):
        try:
            with open(".env") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TELEGRAM_BOT_TOKEN="):
                        telegram_token = line.split("=", 1)[1].strip()
                    elif line.startswith("TELEGRAM_CHAT_ID="):
                        telegram_chat_id = line.split("=", 1)[1].strip()
        except Exception as e:
            print(f"Warning: Tried reading .env file but got error: {e}")

if not telegram_token or not telegram_chat_id:
    print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured.")
    exit(1)

date_str = datetime.date.today().isoformat()
date_compact = date_str.replace("-", "")

def send_telegram_message(text, escape=True):
    print(f"Sending message to Telegram (length: {len(text)})...")
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    formatted_text = html.escape(text) if escape else text
    payload = {
        "chat_id": telegram_chat_id,
        "text": formatted_text,
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
    except Exception as e:
        print(f"Exception sending message: {e}")

def upload_telegram_file(file_path, file_name, caption, file_type="document"):
    if not file_path or not os.path.exists(file_path):
        print(f"Error: file not found: {file_path}")
        return

    print(f"Uploading {file_type} to Telegram: {file_name} ({os.path.getsize(file_path)} bytes)...")
    if file_type == "photo":
        url = f"https://api.telegram.org/bot{telegram_token}/sendPhoto"
        file_key = "photo"
    else:
        url = f"https://api.telegram.org/bot{telegram_token}/sendDocument"
        file_key = "document"

    boundary = b"----TelegramUploadBoundary"
    CRLF = b"\r\n"
    parts = []
    
    parts.append(b"--" + boundary)
    parts.append(b'Content-Disposition: form-data; name="chat_id"')
    parts.append(b"")
    parts.append(telegram_chat_id.encode("utf-8"))
    
    if caption:
        parts.append(b"--" + boundary)
        parts.append(b'Content-Disposition: form-data; name="caption"')
        parts.append(b"")
        parts.append(html.escape(caption).encode("utf-8"))
        
        parts.append(b"--" + boundary)
        parts.append(b'Content-Disposition: form-data; name="parse_mode"')
        parts.append(b"")
        parts.append(b"HTML")

    parts.append(b"--" + boundary)
    parts.append(f'Content-Disposition: form-data; name="{file_key}"; filename="{file_name}"'.encode("utf-8"))
    parts.append(b"Content-Type: application/octet-stream")
    parts.append(b"")
    with open(file_path, "rb") as f:
        parts.append(f.read())
        
    parts.append(b"--" + boundary + b"--")
    parts.append(b"")
    
    body = CRLF.join(parts)
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary.decode('utf-8')}"
    }
    
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as res:
            resp = json.loads(res.read().decode("utf-8"))
            if not resp.get("ok"):
                print(f"Error uploading file: {resp.get('description')}")
            else:
                print(f"File upload completed successfully: {file_name}")
    except Exception as e:
        print(f"Exception uploading file: {e}")

# Parse carousel post text from file
posts = {}
current_key = None
current_content = []

posts_file = f"linkedin_posts_{date_compact}.txt"
if not os.path.exists(posts_file):
    # Fallback to today file
    posts_file = "linkedin_posts_today.txt"

if os.path.exists(posts_file):
    with open(posts_file, encoding="utf-8") as f:
        for line in f:
            if line.startswith("=================================================="):
                continue
            elif line.startswith("3. CAROUSEL"):
                current_key = "carousel"
                current_content = []
            elif line.startswith("1. COLLABORATIVE") or line.startswith("2. POLL") or line.startswith("4. INFOGRAPHIC") or line.startswith("5. POST") or line.startswith("6. POST") or line.startswith("7. POST") or line.startswith("8. POST") or line.startswith("9. POST") or line.startswith("10. POST") or line.startswith("11. POST"):
                current_key = None
            else:
                if current_key:
                    current_content.append(line)
            if current_key:
                posts[current_key] = "".join(current_content).strip()

carousel_caption = ""
if "carousel" in posts:
    caption_lines = []
    capture = False
    for line in posts["carousel"].split("\n"):
        if line.startswith("Caption:") or line.startswith("CAROUSEL CAPTION:"):
            capture = True
            continue
        if line.startswith("Slide 1:") or line.startswith("Slide 1"):
            capture = False
        if capture:
            caption_lines.append(line)
    carousel_caption = "\n".join(caption_lines).strip()

pdf_dir = f"./carousel-routine/output/{date_str}/carousel-branded"
pdf_path = os.path.join(pdf_dir, "startup-strategy-carousel.pdf")
if not os.path.exists(pdf_path):
    pdf_path = None
    if os.path.exists(pdf_dir):
        pdfs = [os.path.join(pdf_dir, fn) for fn in os.listdir(pdf_dir) if fn.endswith(".pdf")]
        if pdfs:
            pdfs.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            pdf_path = pdfs[0]
if not pdf_path:
    pdf_path = f"./carousel-routine/output/{date_str}/carousel-branded/carousel.pdf"

# Notify and send carousel
send_telegram_message(f"🎠 <b>LinkedIn Carousel Drop — {date_str}</b>\nAttached is today's visual carousel PDF and preview slides.", escape=False)

if pdf_path and os.path.exists(pdf_path):
    upload_telegram_file(
        pdf_path, 
        os.path.basename(pdf_path), 
        f"━━━ CAROUSEL PDF ━━━\n\n{carousel_caption}"
    )

if os.path.exists(pdf_dir):
    slide_pngs = sorted([fn for fn in os.listdir(pdf_dir) if fn.startswith("slide-") and fn.endswith(".png")])
    for slide_fn in slide_pngs:
        slide_path = os.path.join(pdf_dir, slide_fn)
        slide_num = slide_fn.split("-")[1].split(".")[0]
        upload_telegram_file(
            slide_path,
            slide_fn,
            f"Slide {slide_num} of {len(slide_pngs)}",
            file_type="photo"
        )

print("Carousel only delivery completed successfully.")
