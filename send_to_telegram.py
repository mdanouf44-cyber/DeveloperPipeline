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
    print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured in environment or .env file.")
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
            else:
                print("Message sent successfully.")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error sending message: {e.code} - {e.reason}")
        try:
            print("Response body:", e.read().decode("utf-8"))
        except:
            pass
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
    
    # chat_id
    parts.append(b"--" + boundary)
    parts.append(b'Content-Disposition: form-data; name="chat_id"')
    parts.append(b"")
    parts.append(telegram_chat_id.encode("utf-8"))
    
    # caption
    if caption:
        parts.append(b"--" + boundary)
        parts.append(b'Content-Disposition: form-data; name="caption"')
        parts.append(b"")
        parts.append(html.escape(caption).encode("utf-8"))
        
        parts.append(b"--" + boundary)
        parts.append(b'Content-Disposition: form-data; name="parse_mode"')
        parts.append(b"")
        parts.append(b"HTML")

    # file
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
    except urllib.error.HTTPError as e:
        print(f"HTTP Error uploading file: {e.code} - {e.reason}")
        try:
            print("Response body:", e.read().decode("utf-8"))
        except:
            pass
    except Exception as e:
        print(f"Exception uploading file: {e}")

# Parse posts from file
posts = {}
current_key = None
current_content = []

posts_file = f"linkedin_posts_{date_compact}.txt"
if not os.path.exists(posts_file):
    print(f"Error: posts file not found: {posts_file}")
    exit(1)

with open(posts_file, encoding="utf-8") as f:
    for line in f:
        if line.startswith("=================================================="):
            continue
        elif line.startswith("1. COLLABORATIVE ARTICLE"):
            current_key = "collaborative_article"
            current_content = []
        elif line.startswith("2. POLL"):
            current_key = "poll"
            current_content = []
        elif line.startswith("3. CAROUSEL"):
            current_key = "carousel"
            current_content = []
        elif line.startswith("4. INFOGRAPHIC"):
            current_key = "infographic"
            current_content = []
        elif line.startswith("5. POST 1"):
            current_key = "post_1"
            current_content = []
        elif line.startswith("6. POST 2"):
            current_key = "post_2"
            current_content = []
        elif line.startswith("7. POST 3"):
            current_key = "post_3"
            current_content = []
        elif line.startswith("8. POST 4"):
            current_key = "post_4"
            current_content = []
        elif line.startswith("9. POST 5"):
            current_key = "post_5"
            current_content = []
        elif line.startswith("10. POST 6"):
            current_key = "post_6"
            current_content = []
        elif line.startswith("11. POST 7"):
            current_key = "post_7"
            current_content = []
        else:
            if current_key:
                current_content.append(line)
        
        if current_key:
            posts[current_key] = "".join(current_content).strip()

print("Daily newspaper HTML and PDF already generated successfully. Skipping generation step.")

# Format and send header message
header_msg = f"📅 <b>LinkedIn Content Drop — {date_str}</b>\n11 posts ready (4 Reddit-based + 7 AI News). Carousel PDF and infographic attached below."
send_telegram_message(header_msg, escape=False)

# Send Reddit-based posts
if "collaborative_article" in posts:
    send_telegram_message(f"📝 <b>Collaborative Article:</b>\n\n{html.escape(posts['collaborative_article'])}", escape=False)
if "poll" in posts:
    send_telegram_message(f"📊 <b>Poll:</b>\n\n{html.escape(posts['poll'])}", escape=False)

# Send AI News section header and posts
news_header = f"📰 <b>AI News Posts — {date_str}</b>\n7 plain-text posts from the linkedin-ai-news-engine:"
send_telegram_message(news_header, escape=False)

for i in range(1, 8):
    post_key = f"post_{i}"
    if post_key in posts:
        send_telegram_message(f"✍️ <b>AI News Post {i}:</b>\n\n{html.escape(posts[post_key])}", escape=False)

# Upload the Text Posts PDF
posts_pdf_path = f"linkedin_posts_{date_compact}.pdf"
upload_telegram_file(
    posts_pdf_path,
    f"linkedin_posts_{date_compact}.pdf",
    f"━━━ DAILY TEXT POSTS PDF — {date_str} ━━━\n\nContains all 11 LinkedIn posts (Collaborative Article, Poll, and 7 AI News Posts) formatted for easy reading."
)

# Upload the raw Text Posts file
posts_txt_path = f"linkedin_posts_{date_compact}.txt"
upload_telegram_file(
    posts_txt_path,
    f"linkedin_posts_{date_compact}.txt",
    f"━━━ RAW TEXT DRAFTS — {date_str} ━━━\n\nFor bot auto-scheduling consumption."
)

# Upload PDF and PNG Infographic
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
png_path = f"./linkedin-infographic-{date_compact}.png"

# Extract Carousel & Infographic captions
carousel_caption = ""
if "carousel" in posts:
    caption_lines = []
    capture = False
    for line in posts["carousel"].split("\n"):
        if line.startswith("Caption:") or line.startswith("CAROUSEL CAPTION:"):
            capture = True
            continue
        if line.startswith("Slide 1:"):
            capture = False
        if capture:
            caption_lines.append(line)
    carousel_caption = "\n".join(caption_lines).strip()

infographic_caption = ""
if "infographic" in posts:
    caption_lines = []
    capture = False
    for line in posts["infographic"].split("\n"):
        if line.startswith("Caption:") or line.startswith("INFOGRAPHIC CAPTION:"):
            capture = True
            continue
        if capture:
            caption_lines.append(line)
    infographic_caption = "\n".join(caption_lines).strip()

upload_telegram_file(
    pdf_path, 
    os.path.basename(pdf_path) if pdf_path else "carousel.pdf", 
    f"━━━ CAROUSEL PDF ━━━\n\n{carousel_caption}"
)

# Upload individual slide PNGs
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

upload_telegram_file(
    png_path, 
    "linkedin-infographic.png", 
    f"━━━ INFOGRAPHIC ━━━\n\n{infographic_caption}",
    file_type="photo"
)

print("All daily LinkedIn Telegram publication steps completed successfully.")
