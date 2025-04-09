import json
import uuid
import pytz
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os

# Читаем список администраторов (если понадобится для уведомлений в данном файле)
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x]

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

def ensure_temp_broadcast(broadcast_id):
    temp_data = load_temp_broadcast()
    if broadcast_id not in temp_data:
        broadcasts = load_broadcasts()
        if broadcast_id in broadcasts:
            temp_data[broadcast_id] = broadcasts[broadcast_id]
            save_temp_broadcast(temp_data)
    return temp_data

def init_broadcast(bot, admin_ids, scheduler):
    @bot.message_handler(commands=["рассылка"])
    def handle_broadcast(message):
        # Проверка администратора производится в main.py,
        # поэтому здесь предполагается, что сообщение пришло от администратора.
        bot.send_message(message.chat.id, "📣 Введите текст для рассылки:")
        bot.register_next_step_handler(message, get_broadcast_text)
    
    def get_broadcast_text(message):
        text = message.text
        broadcast_id = str(uuid.uuid4())
        draft = {
            "text": text,
            "file_id": None,
            "media_type": None,
            "link": "",
            "delivered": 0
        }
        temp_data = load_temp_broadcast()
        temp_data[broadcast_id] = draft
        save_temp_broadcast(temp_data)
        bot.send_message(message.chat.id, "📎 Прикрепите файл (или введите 'нет'/'не'):")
        bot.register_next_step_handler(message, get_broadcast_file, broadcast_id)
    
    def get_broadcast_file(message, broadcast_id):
        temp_data = load_temp_broadcast()
        if broadcast_id not in temp_data:
            bot.send_message(message.chat.id, "❌ Черновик не найден.")
            return
        draft = temp_data[broadcast_id]
        file_id = None
        media_type = None

        if message.text and message.text.lower() in ["нет", "не"]:
            pass
        elif message.document:
            file_id = message.document.file_id
            media_type = "document"
        elif message.audio:
            file_id = message.audio.file_id
            media_type = "audio"
        elif message.video:
            file_id = message.video.file_id
            media_type = "video"
        elif message.photo:
            file_id = message.photo[-1].file_id
            media_type = "photo"
        elif message.video_note:
            file_id = message.video_note.file_id
            media_type = "video_note"
        else:
            bot.send_message(message.chat.id, "❌ Неверный тип файла. Прикрепите файл или введите 'нет'/'не'.")
            return
        
        draft["file_id"] = file_id
        draft["media_type"] = media_type
        temp_data[broadcast_id] = draft
        save_temp_broadcast(temp_data)
        bot.send_message(message.chat.id, "🔗 Вставьте ссылку (или введите 'нет'/'не'):")
        bot.register_next_step_handler(message, get_broadcast_link, broadcast_id)
    
    def get_broadcast_link(message, broadcast_id):
        temp_data = load_temp_broadcast()
        if broadcast_id not in temp_data:
            bot.send_message(message.chat.id, "❌ Черновик не найден.")
            return
        if message.content_type != "text":
            bot.send_message(message.chat.id, "❌ Это не текст. Попробуйте ещё раз (или введите 'нет'/'не').")
            bot.register_next_step_handler(message, get_broadcast_link, broadcast_id)
            return
        
        link_text = message.text.strip()
        if link_text.lower() in ["нет", "не"]:
            link_text = ""
        draft = temp_data[broadcast_id]
        draft["link"] = link_text
        temp_data[broadcast_id] = draft
        save_temp_broadcast(temp_data)
        send_broadcast_preview(message.chat.id, broadcast_id, draft)
    
    def send_broadcast_preview(chat_id, broadcast_id, draft):
        text = draft["text"]
        link = draft.get("link", "")
        file_id = draft.get("file_id")
        media_type = draft.get("media_type")
        preview_text = f"📢 <b>Предпросмотр рассылки</b>\n\n{text}"
        if link:
            preview_text += f"\n\n🔗 <a href='{link}'>Перейти по ссылке</a>"

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✏️ Изменить текст", callback_data=f"broadcast_edit_text|{broadcast_id}"))
        markup.add(InlineKeyboardButton("✏️ Изменить файл", callback_data=f"broadcast_edit_file|{broadcast_id}"))
        markup.add(InlineKeyboardButton("✏️ Изменить ссылку", callback_data=f"broadcast_edit_link|{broadcast_id}"))
        markup.add(InlineKeyboardButton("❌ Удалить черновик", callback_data=f"broadcast_delete|{broadcast_id}"))
        markup.add(InlineKeyboardButton("✅ Сохранить", callback_data=f"broadcast_save|{broadcast_id}"))

        if file_id:
            if media_type == "photo":
                bot.send_photo(chat_id, file_id, caption=preview_text, parse_mode="HTML", reply_markup=markup)
            elif media_type == "audio":
                bot.send_audio(chat_id, file_id, caption=preview_text, parse_mode="HTML", reply_markup=markup)
            elif media_type == "video":
                bot.send_video(chat_id, file_id, caption=preview_text, parse_mode="HTML", reply_markup=markup)
            elif media_type == "video_note":
                bot.send_video_note(chat_id, file_id, reply_markup=markup)
            else:
                bot.send_document(chat_id, file_id, caption=preview_text, parse_mode="HTML", reply_markup=markup)
        else:
            bot.send_message(chat_id, preview_text, parse_mode="HTML", reply_markup=markup)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_edit_text"))
    def broadcast_edit_text(call):
        _, broadcast_id = call.data.split("|", 1)
        ensure_temp_broadcast(broadcast_id)
        msg = bot.send_message(call.message.chat.id, "✏️ Введите новый текст для рассылки:")
        bot.register_next_step_handler(msg, broadcast_update_text, broadcast_id)
    
    def broadcast_update_text(message, broadcast_id):
        temp_data = ensure_temp_broadcast(broadcast_id)
        if broadcast_id not in temp_data:
            bot.send_message(message.chat.id, "❌ Черновик не найден.")
            return
        temp_data[broadcast_id]["text"] = message.text
        save_temp_broadcast(temp_data)
        send_broadcast_preview(message.chat.id, broadcast_id, temp_data[broadcast_id])
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_edit_file"))
    def broadcast_edit_file(call):
        _, broadcast_id = call.data.split("|", 1)
        ensure_temp_broadcast(broadcast_id)
        msg = bot.send_message(call.message.chat.id, "📎 Прикрепите новый файл (или введите 'нет'/'не' для удаления):")
        bot.register_next_step_handler(msg, broadcast_update_file, broadcast_id)
    
    def broadcast_update_file(message, broadcast_id):
        temp_data = ensure_temp_broadcast(broadcast_id)
        if broadcast_id not in temp_data:
            bot.send_message(message.chat.id, "❌ Черновик не найден.")
            return
        draft = temp_data[broadcast_id]
        if message.text and message.text.lower() in ["нет", "не"]:
            draft["file_id"] = None
            draft["media_type"] = None
        elif message.document:
            draft["file_id"] = message.document.file_id
            draft["media_type"] = "document"
        elif message.audio:
            draft["file_id"] = message.audio.file_id
            draft["media_type"] = "audio"
        elif message.video:
            draft["file_id"] = message.video.file_id
            draft["media_type"] = "video"
        elif message.photo:
            draft["file_id"] = message.photo[-1].file_id
            draft["media_type"] = "photo"
        elif message.video_note:
            draft["file_id"] = message.video_note.file_id
            draft["media_type"] = "video_note"
        else:
            bot.send_message(message.chat.id, "❌ Неверный тип файла. Попробуйте ещё раз или введите 'нет'/'не'.")
            return
        temp_data[broadcast_id] = draft
        save_temp_broadcast(temp_data)
        send_broadcast_preview(message.chat.id, broadcast_id, draft)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_edit_link"))
    def broadcast_edit_link(call):
        _, broadcast_id = call.data.split("|", 1)
        ensure_temp_broadcast(broadcast_id)
        msg = bot.send_message(call.message.chat.id, "🔗 Введите новую ссылку (или введите 'нет'/'не' для удаления):")
        bot.register_next_step_handler(msg, broadcast_update_link, broadcast_id)
    
    def broadcast_update_link(message, broadcast_id):
        if message.content_type != "text":
            bot.send_message(message.chat.id, "❌ Это не текст. Попробуйте ещё раз.")
            bot.register_next_step_handler(message, broadcast_update_link, broadcast_id)
            return
        temp_data = ensure_temp_broadcast(broadcast_id)
        if broadcast_id not in temp_data:
            bot.send_message(message.chat.id, "❌ Черновик не найден.")
            return
        link_text = message.text.strip()
        if link_text.lower() in ["нет", "не"]:
            link_text = ""
        temp_data[broadcast_id]["link"] = link_text
        save_temp_broadcast(temp_data)
        send_broadcast_preview(message.chat.id, broadcast_id, temp_data[broadcast_id])
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_delete"))
    def broadcast_delete(call):
        _, broadcast_id = call.data.split("|", 1)
        temp_data = load_temp_broadcast()
        if broadcast_id in temp_data:
            del temp_data[broadcast_id]
            save_temp_broadcast(temp_data)
            bot.send_message(call.message.chat.id, "🗑️ Черновик удалён.")
        else:
            bot.send_message(call.message.chat.id, "❌ Черновик не найден.")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_save"))
    def broadcast_save(call):
        _, broadcast_id = call.data.split("|", 1)
        temp_data = load_temp_broadcast()
        if broadcast_id not in temp_data:
            bot.send_message(call.message.chat.id, "❌ Черновик не найден.")
            return
        broadcasts = load_broadcasts()
        broadcasts[broadcast_id] = temp_data[broadcast_id]
        save_broadcasts(broadcasts)
        if broadcast_id in temp_data:
            del temp_data[broadcast_id]
        save_temp_broadcast(temp_data)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚀 Отправить сейчас", callback_data=f"broadcast_send_now|{broadcast_id}"))
        markup.add(InlineKeyboardButton("🕰 Запланировать на дату", callback_data=f"broadcast_schedule|{broadcast_id}"))
        bot.send_message(call.message.chat.id, "✅ Черновик сохранён. Выберите действие:", reply_markup=markup)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_send_now"))
    def broadcast_send_now(call):
        _, broadcast_id = call.data.split("|", 1)
        broadcasts = load_broadcasts()
        broadcast = broadcasts.get(broadcast_id)
        if not broadcast:
            bot.send_message(call.message.chat.id, "❌ Рассылка не найдена.")
            return
        count = do_broadcast(bot, broadcast)
        broadcast["delivered"] = count
        broadcasts[broadcast_id] = broadcast
        save_broadcasts(broadcasts)
        bot.send_message(call.message.chat.id, f"✅ Рассылка отправлена {count} пользователям!")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_schedule"))
    def broadcast_schedule(call):
        _, broadcast_id = call.data.split("|", 1)
        msg = bot.send_message(call.message.chat.id, "🕰 Введите дату и время в формате ДД.ММ.ГГ ЧЧ:ММ (МСК), например: 25.03.25 15:30")
        bot.register_next_step_handler(msg, broadcast_schedule_time, broadcast_id)
    
    def broadcast_schedule_time(message, broadcast_id):
        broadcasts = load_broadcasts()
        broadcast = broadcasts.get(broadcast_id)
        if not broadcast:
            bot.send_message(message.chat.id, "❌ Рассылка не найдена.")
            return
        time_str = message.text.strip()
        try:
            # Формат ДД.ММ.ГГ ЧЧ:ММ
            run_date = datetime.strptime(time_str, "%d.%m.%y %H:%M")
            run_date = MSK_TZ.localize(run_date)
            now_msk = datetime.now(MSK_TZ)
            if run_date <= now_msk:
                bot.send_message(message.chat.id, "❌ Укажите дату и время в будущем (МСК).")
                bot.register_next_step_handler(message, broadcast_schedule_time, broadcast_id)
                return
            run_date_utc = run_date.astimezone(pytz.utc)
        except Exception:
            msg = bot.send_message(message.chat.id, "❌ Неверный формат. Попробуйте ещё раз (например: 25.03.25 15:30).")
            bot.register_next_step_handler(msg, broadcast_schedule_time, broadcast_id)
            return
        
        job = scheduler.add_job(do_scheduled_broadcast, 'date', run_date=run_date_utc, args=[bot, broadcast_id])
        scheduled = load_scheduled()
        scheduled.append({
            "job_id": job.id,
            "broadcast_id": broadcast_id,
            "run_date": run_date_utc.isoformat(),
            "status": "scheduled"
        })
        save_scheduled(scheduled)
        bot.send_message(message.chat.id, f"📅 Рассылка запланирована на {run_date.strftime('%d.%m.%y %H:%M')} (МСК).")

def do_scheduled_broadcast(bot, broadcast_id):
    from main import ADMIN_IDS  # импортируем список администраторов из main.py
    broadcasts = load_broadcasts()
    broadcast = broadcasts.get(broadcast_id)
    if not broadcast:
        return
    count = do_broadcast(bot, broadcast)
    broadcast["delivered"] = count
    broadcasts[broadcast_id] = broadcast
    save_broadcasts(broadcasts)

    scheduled = load_scheduled()
    for item in scheduled:
        if item["broadcast_id"] == broadcast_id and item["status"] == "scheduled":
            item["status"] = "done"
    save_scheduled(scheduled)

    print(f"[SCHEDULED] Рассылка {broadcast_id} отправлена {count} пользователям.")
    bot.send_message(ADMIN_IDS[0], f"📢 Рассылка {broadcast_id} выполнена и отправлена {count} пользователям.")

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
                elif media_type == "video_note":
                    bot.send_video_note(user["id"], file_id)
                else:
                    bot.send_document(user["id"], file_id, caption=final_text)
            else:
                bot.send_message(user["id"], final_text)
            count += 1
        except Exception as e:
            print(f"Ошибка при отправке пользователю {user['id']}: {e}")
    return count

def restore_scheduled_jobs(scheduler, bot):
    scheduled = load_scheduled()
    for item in scheduled:
        if item["status"] == "scheduled":
            broadcast_id = item["broadcast_id"]
            run_date_str = item["run_date"]
            try:
                run_date = datetime.fromisoformat(run_date_str)
                scheduler.add_job(
                    do_scheduled_broadcast,
                    'date',
                    run_date=run_date,
                    args=[bot, broadcast_id],
                    id=item["job_id"]
                )
            except Exception as e:
                print(f"Не удалось восстановить задачу {broadcast_id}: {e}")


