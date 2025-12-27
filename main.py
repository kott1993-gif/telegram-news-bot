import feedparser
import hashlib
import time
import sqlite3
import os
import requests
from openai import OpenAI

# ====== НАСТРОЙКИ (КЛЮЧИ ДОБАВИМ В RAILWAY) ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# !!! ОБЯЗАТЕЛЬНО !!!
# Впиши username своего канала, например: @news_world_cat
CHANNEL_ID = "@kotsnovosti"

RSS_FEEDS = [
    "https://ria.ru/export/rss2/politics/index.xml",
    "https://tass.ru/rss/v2.xml",
    "https://www.interfax.ru/rss.asp",
    "https://www.aljazeera.com/xml/rss/all.xml"
]

# =================================================

client = OpenAI(api_key=OPENAI_API_KEY)

# --- база для защиты от повторов ---
conn = sqlite3.connect("news.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS published (
    hash TEXT PRIMARY KEY
)
""")
conn.commit()


def is_published(text):
    h = hashlib.md5(text.encode("utf-8")).hexdigest()
    cursor.execute("SELECT 1 FROM published WHERE hash=?", (h,))
    return cursor.fetchone() is not None


def mark_published(text):
    h = hashlib.md5(text.encode("utf-8")).hexdigest()
    cursor.execute("INSERT OR IGNORE INTO published VALUES (?)", (h,))
    conn.commit()


def rewrite_news(title, summary):
    prompt = f"""
Сделай краткий, нейтральный новостной пересказ на русском языке.
3–4 предложения.
Без пропаганды, без оценок, сухой новостной стиль.

Новость:
{title}
{summary}
"""
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def generate_image(topic):
    prompt = f"""
Мультяшная новостная иллюстрация.
Тема: {topic}.
Стиль: flat illustration, понятный сюжет.
Нейтральные цвета.
Без насилия.
Небольшой кот-репортёр на фоне.
"""
    img = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024"
    )
    return img.data[0].url


def post_to_telegram(text, image_url):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHANNEL_ID,
        "photo": image_url,
        "caption": text,
        "parse_mode": "HTML"
    }
    requests.post(url, data=payload)


# ====== ОСНОВНОЙ ЦИКЛ ======
while True:
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:5]:
            base_text = entry.title + entry.get("summary", "")

            if is_published(base_text):
                continue

            news_text = rewrite_news(
                entry.title,
                entry.get("summary", "")
            )

            image_url = generate_image(entry.title)

            final_post = f"""🐱🗞 <b>Политика / Мир</b>

{news_text}

Источник: {feed.feed.title} 😺
"""

            post_to_telegram(final_post, image_url)
            mark_published(base_text)

            time.sleep(20)

    time.sleep(600)
