import json
import uuid
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import pytz

BROADCAST_FILE = "broadcasts.json"
TEMP_BROADCAST_FILE = "temp_broadcasts.json"
SCHEDULED_BROADCAST_FILE = "scheduled_broadcasts.json"
USER_FILE = "user_db.json"

MSK_TZ = pytz.timezone("Europe/Moscow")

def load_temp_broadcast():
    try:
        with open(TEMP_BROADCAST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_temp_broadcast(data):
    with open(TEMP_BROADCAST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def load_broadcasts():
    try:
        with open(BROADCAST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_broadcasts(data):
    with open(BROADCAST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def load_scheduled():
    try:
        with open(SCHEDULED_BROADCAST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_scheduled(data):
    with open(SCHEDULED_BROADCAST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

# Все остальные функции, включая init_broadcast, остаются как есть и подключаются в main.py

# Добавляем также do_scheduled_broadcast и do_broadcast

def do_scheduled_broadcast(bot, broadcast_id):
    broadcasts = load_broadcasts()
    broadcast = broadcasts.get(broadcast_id)
    if not broadcast:
        return

    count = do_broadcast(bot, broadcast)

    scheduled = load_scheduled()
    for item in scheduled:
        if item["broadcast_id"] == broadcast_id and item["status"] == "scheduled":
            item["status"] = "done"
    save_scheduled(scheduled)

    print(f"[SCHEDULED] Рассылка {broadcast_id} отправлена {count} пользователям.")

def do_broadcast(bot, broadcast):
    text = broadcast["text"]
    file_id = broadcast.get("file_id")
    media_type = broadcast.get("media_type")
    link = broadcast.get("link")

    try:
        with open(USER_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
    except:
        users = []

    count = 0
    for user in users:
        try:
            final_text = text
            if link:
                final_text += f"\n\n🔗 {link}"
            if file_id:
                if media_type == "photo":
                    bot.send_photo(user["id"], file_id, caption=final_text)
                elif media_type == "audio":
                    bot.send_audio(user["id"], file_id, caption=final_text)
                elif media_type == "video":
                    bot.send_video(user["id"], file_id, caption=final_text)
                else:
                    bot.send_document(user["id"], file_id, caption=final_text)
            else:
                bot.send_message(user["id"], final_text)
            count += 1
        except Exception as e:
            print(f"Ошибка при отправке пользователю {user['id']}: {e}")

    return count
