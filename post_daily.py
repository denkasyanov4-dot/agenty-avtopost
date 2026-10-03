import os
import sys
import json
import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = "@ii_na_skladah"
QUEUE_FILE = "queue.txt"
SEPARATOR = "\n---\n"
IMAGES_DIR = ""
API = f"https://api.telegram.org/bot{TOKEN}"

# Формат шапки поста (каждая строка в квадратных скобках, в самом начале поста):
#   [IMAGE: a.jpg]                 — одна картинка (как раньше)
#   [IMAGES: a.jpg, b.png, c.png]  — альбом из 2–10 картинок
#   [FILE: kalkulyator.xlsx]       — файл, который уйдёт отдельным сообщением после текста
# Все строки шапки необязательны. Текст поста начинается с первой строки без [ ... ].


def split_posts(raw):
    """Делит очередь на посты по строке '---'. Строки '---' внутри блоков <pre> (например,
    в шаблонах SKILL.md) разделителем не считаются."""
    posts, cur, depth = [], [], 0
    for line in raw.split("\n"):
        if line.strip() == "---" and depth == 0:
            posts.append("\n".join(cur)); cur = []
            continue
        cur.append(line)
        depth += line.count("<pre>") - line.count("</pre>")
        depth = max(depth, 0)
    posts.append("\n".join(cur))
    return [p.strip() for p in posts if p.strip()]


def parse_post(post):
    lines = post.split("\n")
    images, files = [], []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not (line.startswith("[") and line.endswith("]") and ":" in line):
            break
        key, value = line[1:-1].split(":", 1)
        key = key.strip().upper()
        names = [v.strip() for v in value.split(",") if v.strip()]
        if key in ("IMAGE", "IMAGES"):
            images.extend(names)
        elif key == "FILE":
            files.extend(names)
        else:
            break
        i += 1
    text = "\n".join(lines[i:]).strip()
    return images, files, text


def existing(names):
    found = []
    for name in names:
        path = os.path.join(IMAGES_DIR, name)
        if os.path.exists(path):
            found.append(path)
        else:
            print(f"WARNING: {path} not found, skipping it.")
    return found


def check(resp, what):
    if resp.status_code != 200:
        print(f"Telegram API error ({what}): {resp.status_code} {resp.text}")
        sys.exit(1)


def send_images(paths):
    if len(paths) == 1:
        with open(paths[0], "rb") as f:
            resp = requests.post(f"{API}/sendPhoto", data={"chat_id": CHAT_ID},
                                 files={"photo": f}, timeout=60)
        check(resp, "photo")
        return
    media, files = [], {}
    for n, path in enumerate(paths[:10]):
        key = f"photo{n}"
        media.append({"type": "photo", "media": f"attach://{key}"})
        files[key] = open(path, "rb")
    try:
        resp = requests.post(f"{API}/sendMediaGroup",
                             data={"chat_id": CHAT_ID, "media": json.dumps(media)},
                             files=files, timeout=120)
    finally:
        for f in files.values():
            f.close()
    check(resp, "album")


def send_files(paths):
    for path in paths:
        with open(path, "rb") as f:
            resp = requests.post(f"{API}/sendDocument", data={"chat_id": CHAT_ID},
                                 files={"document": f}, timeout=60)
        check(resp, "file")


def main():
    if not os.path.exists(QUEUE_FILE):
        print(f"{QUEUE_FILE} not found — nothing to post.")
        sys.exit(0)

    with open(QUEUE_FILE, encoding="utf-8") as f:
        raw = f.read()

    posts = split_posts(raw)
    if not posts:
        print("Queue is empty — add more posts to queue.txt.")
        sys.exit(0)

    image_names, file_names, post_text = parse_post(posts[0])
    image_paths = existing(image_names)
    file_paths = existing(file_names)

    if len(post_text) > 4096:
        print(f"WARNING: post text is {len(post_text)} chars, Telegram may reject it.")

    if image_paths:
        send_images(image_paths)

    resp = requests.post(f"{API}/sendMessage", data={
        "chat_id": CHAT_ID,
        "text": post_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }, timeout=30)
    check(resp, "text")

    if file_paths:
        send_files(file_paths)

    print("Posted successfully:")
    print(post_text[:80] + "...")

    # Пост ушёл — картинки и файлы больше не нужны, удаляем, чтобы репозиторий не зарастал.
    for path in image_paths + file_paths:
        try:
            os.remove(path)
            print(f"Deleted used file: {path}")
        except OSError as e:
            print(f"WARNING: could not delete {path}: {e}")

    remaining = posts[1:]
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        f.write(SEPARATOR.join(remaining))

    if not remaining:
        print("WARNING: queue is now empty after this post — add more posts soon.")


if __name__ == "__main__":
    main()
