import os
import sys
import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = "@ii_na_skladah"
QUEUE_FILE = "queue.txt"
SEPARATOR = "\n---\n"
IMAGES_DIR = "images"

def main():
    if not os.path.exists(QUEUE_FILE):
        print(f"{QUEUE_FILE} not found — nothing to post.")
        sys.exit(0)

    with open(QUEUE_FILE, encoding="utf-8") as f:
        raw = f.read()

    posts = [p.strip() for p in raw.split(SEPARATOR) if p.strip()]

    if not posts:
        print("Queue is empty — add more posts to queue.txt.")
        sys.exit(0)

    post_text = posts[0]
    image_path = None

    lines = post_text.split("\n")
    if lines[0].startswith("[IMAGE:") and lines[0].endswith("]"):
        image_file = lines[0][len("[IMAGE:"):-1].strip()
        post_text = "\n".join(lines[1:]).strip()
        candidate = os.path.join(IMAGES_DIR, image_file)
        if os.path.exists(candidate):
            image_path = candidate
        else:
            print(f"WARNING: image {candidate} not found, posting text only.")

    if image_path:
        with open(image_path, "rb") as photo:
            resp = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                data={"chat_id": CHAT_ID},
                files={"photo": photo},
                timeout=60,
            )
        if resp.status_code != 200:
            print(f"Telegram API error (photo): {resp.status_code} {resp.text}")
            sys.exit(1)

    resp = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": post_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        },
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"Telegram API error: {resp.status_code} {resp.text}")
        sys.exit(1)

    print("Posted successfully:")
    print(post_text[:80] + "...")

    remaining = posts[1:]
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        f.write(SEPARATOR.join(remaining))

    if not remaining:
        print("WARNING: queue is now empty after this post — add more posts soon.")

if __name__ == "__main__":
    main()
