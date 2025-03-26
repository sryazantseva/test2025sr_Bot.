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

def load_json(file, default):
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def init_broadcast(bot, admin_id, scheduler):
    @bot.message_handler(commands=["рассылка"])
    def handle_broadcast(message):
        if message.from_user.id != admin_id:
            return
        msg = bot.send_message(message.chat.id, "📣 Введите текст для рассылки:")
        bot.register_next_step_handler(msg, get_text)

    def get_text(message):
        bid = str(uuid.uuid4())
        draft = {"text": message.text, "file_id": None, "media": None, "link": ""}
        temp = load_json(TEMP_BROADCAST_FILE, {})
        temp[bid] = draft
        save_json(TEMP_BROADCAST_FILE, temp)
        bot.send_message(message.chat.id, "📎 Прикрепите файл (или 'нет'):")
        bot.register_next_step_handler(message, get_file, bid)

    def get_file(message, bid):
        temp = load_json(TEMP_BROADCAST_FILE, {})
        if bid not in temp:
            return
        draft = temp[bid]
        t = message
        if t.text and t.text.lower() in ["нет", "не"]:
            pass
        elif t.document:
            draft["file_id"] = t.document.file_id
            draft["media"] = "document"
        elif t.audio:
            draft["file_id"] = t.audio.file_id
            draft["media"] = "audio"
        elif t.video:
            draft["file_id"] = t.video.file_id
            draft["media"] = "video"
        elif t.photo:
            draft["file_id"] = t.photo[-1].file_id
            draft["media"] = "photo"
        else:
            bot.send_message(message.chat.id, "❌ Неверный файл. Прикрепите или напишите 'нет'.")
            return
        temp[bid] = draft
        save_json(TEMP_BROADCAST_FILE, temp)
        bot.send_message(message.chat.id, "🔗 Вставьте ссылку (или 'нет'):")
        bot.register_next_step_handler(message, get_link, bid)

    def get_link(message, bid):
        temp = load_json(TEMP_BROADCAST_FILE, {})
        if bid not in temp:
            return
        draft = temp[bid]
        if message.text.lower() not in ["нет", "не"]:
            draft["link"] = message.text.strip()
        temp[bid] = draft
        save_json(TEMP_BROADCAST_FILE, temp)
        preview(message.chat.id, bid, draft)

    def preview(chat_id, bid, d):
        txt = f"<b>📢 Предпросмотр:</b>\n\n{d['text']}"
        if d.get("link"):
            txt += f"\n\n🔗 <a href='{d['link']}'>Ссылка</a>"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Сохранить", callback_data=f"save|{bid}"))
        markup.add(InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_text|{bid}"))
        markup.add(InlineKeyboardButton("❌ Удалить", callback_data=f"delete|{bid}"))
        if d.get("file_id"):
            m = d["media"]
            if m == "photo":
                bot.send_photo(chat_id, d["file_id"], caption=txt, parse_mode="HTML", reply_markup=markup)
            elif m == "audio":
                bot.send_audio(chat_id, d["file_id"], caption=txt, parse_mode="HTML", reply_markup=markup)
            elif m == "video":
                bot.send_video(chat_id, d["file_id"], caption=txt, parse_mode="HTML", reply_markup=markup)
            else:
                bot.send_document(chat_id, d["file_id"], caption=txt, parse_mode="HTML", reply_markup=markup)
        else:
            bot.send_message(chat_id, txt, parse_mode="HTML", reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("save|"))
    def handle_save(call):
        bid = call.data.split("|")[1]
        temp = load_json(TEMP_BROADCAST_FILE, {})
        all_b = load_json(BROADCAST_FILE, {})
        if bid not in temp:
            return
        all_b[bid] = temp[bid]
        save_json(BROADCAST_FILE, all_b)
        temp.pop(bid)
        save_json(TEMP_BROADCAST_FILE, temp)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚀 Отправить", callback_data=f"now|{bid}"))
        markup.add(InlineKeyboardButton("🕒 Запланировать", callback_data=f"schedule|{bid}"))
        bot.send_message(call.message.chat.id, "✅ Сохранено. Выберите действие:", reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("now|"))
    def send_now(call):
        bid = call.data.split("|")[1]
        all_b = load_json(BROADCAST_FILE, {})
        if bid not in all_b:
            return
        count = do_broadcast(bot, all_b[bid])
        bot.send_message(call.message.chat.id, f"✅ Отправлено {count} пользователям.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("schedule|"))
    def ask_time(call):
        bid = call.data.split("|")[1]
        msg = bot.send_message(call.message.chat.id, "Введите время ЧЧ:ММ (МСК) на завтра")
        bot.register_next_step_handler(msg, schedule_send, bid)

    def schedule_send(message, bid):
        all_b = load_json(BROADCAST_FILE, {})
        if bid not in all_b:
            return
        try:
            h, m = map(int, message.text.strip().split(":"))
            now = datetime.now(MSK_TZ)
            run_dt = now.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(days=1)
            job = scheduler.add_job(do_broadcast, 'date', run_date=run_dt, args=[bot, all_b[bid]])
            bot.send_message(message.chat.id, f"📅 Запланировано на {run_dt.strftime('%d.%m %H:%M')} МСК")
        except:
            bot.send_message(message.chat.id, "❌ Неверный формат. Попробуйте ещё раз.")


def do_broadcast(bot, data):
    try:
        users = load_json(USER_FILE, [])
    except:
        return 0
    text = data["text"] + (f"\n\n🔗 {data['link']}" if data.get("link") else "")
    fid = data.get("file_id")
    m = data.get("media")
    count = 0
    for u in users:
        try:
            if fid:
                if m == "photo":
                    bot.send_photo(u["id"], fid, caption=text)
                elif m == "audio":
                    bot.send_audio(u["id"], fid, caption=text)
                elif m == "video":
                    bot.send_video(u["id"], fid, caption=text)
                else:
                    bot.send_document(u["id"], fid, caption=text)
            else:
                bot.send_message(u["id"], text)
            count += 1
        except:
            continue
    return count

