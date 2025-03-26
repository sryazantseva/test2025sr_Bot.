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

def init_broadcast(bot, admin_id, scheduler):
    """
    Инициализация логики рассылок:
    - Создание/редактирование черновиков
    - Сохранение финальных рассылок
    - Планирование через APScheduler
    - Просмотр/удаление/редактирование запланированных рассылок
    """

    # --------------------------------------
    # 1. Команда /рассылка для создания
    # --------------------------------------
    @bot.message_handler(commands=["рассылка"])
    def handle_broadcast(message):
        if message.from_user.id != admin_id:
            return
        bot.send_message(message.chat.id, "📣 Введите текст для рассылки:")
        bot.register_next_step_handler(message, get_broadcast_text)

    def get_broadcast_text(message):
        text = message.text
        broadcast_id = str(uuid.uuid4())
        draft = {"text": text, "file_id": None, "media_type": None, "link": ""}
        temp_data = load_temp_broadcast()
        temp_data[broadcast_id] = draft
        save_temp_broadcast(temp_data)

        bot.send_message(message.chat.id, "📎 Прикрепите файл (или напишите 'нет'/'не'):")
        bot.register_next_step_handler(message, get_broadcast_file, broadcast_id)

    def get_broadcast_file(message, broadcast_id):
        temp_data = load_temp_broadcast()
        if broadcast_id not in temp_data:
            bot.send_message(message.chat.id, "❌ Черновик не найден.")
            return

        draft = temp_data[broadcast_id]
        file_id = None
        media_type = None

        # Приводим текст к нижнему регистру для проверки
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
        else:
            bot.send_message(message.chat.id, "❌ Неверный тип файла. Прикрепите файл или введите 'нет'/'не'.")
            return

        draft["file_id"] = file_id
        draft["media_type"] = media_type
        temp_data[broadcast_id] = draft
        save_temp_broadcast(temp_data)

        bot.send_message(message.chat.id, "🔗 Вставьте ссылку (или напишите 'нет'/'не'):")
        bot.register_next_step_handler(message, get_broadcast_link, broadcast_id)

    def get_broadcast_link(message, broadcast_id):
        temp_data = load_temp_broadcast()
        if broadcast_id not in temp_data:
            bot.send_message(message.chat.id, "❌ Черновик не найден.")
            return

        # Если пользователь отправил медиа вместо текста
        if message.content_type != "text":
            bot.send_message(message.chat.id, "❌ Вы отправили файл, а не ссылку. Попробуйте ещё раз (или 'нет'/'не').")
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

    # --------------------------------------
    # 2. Предпросмотр + inline-кнопки
    # --------------------------------------
    def send_broadcast_preview(chat_id, broadcast_id, draft):
        text = draft["text"]
        link = draft.get("link", "")
        file_id = draft.get("file_id")
        media_type = draft.get("media_type")

        preview_text = f"📢 <b>Предпросмотр рассылки</b>\n\n{text}"
        if link:
            preview_text += f"\n\n🔗 <a href='{link}'>Перейти по ссылке</a>"

        markup = InlineKeyboardMarkup()
        # Кнопки идут по одной в строке, чтобы были "вертикально"
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
            else:
                bot.send_document(chat_id, file_id, caption=preview_text, parse_mode="HTML", reply_markup=markup)
        else:
            bot.send_message(chat_id, preview_text, parse_mode="HTML", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_edit_text"))
    def broadcast_edit_text(call):
        _, broadcast_id = call.data.split("|", 1)
        msg = bot.send_message(call.message.chat.id, "✏️ Введите новый текст для рассылки:")
        bot.register_next_step_handler(msg, broadcast_update_text, broadcast_id)

    def broadcast_update_text(message, broadcast_id):
        temp_data = load_temp_broadcast()
        if broadcast_id not in temp_data:
            bot.send_message(message.chat.id, "❌ Черновик не найден.")
            return
        temp_data[broadcast_id]["text"] = message.text
        save_temp_broadcast(temp_data)
        send_broadcast_preview(message.chat.id, broadcast_id, temp_data[broadcast_id])

    @bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_edit_file"))
    def broadcast_edit_file(call):
        _, broadcast_id = call.data.split("|", 1)
        msg = bot.send_message(call.message.chat.id, "📎 Прикрепите новый файл (или напишите 'нет'/'не' для удаления):")
        bot.register_next_step_handler(msg, broadcast_update_file, broadcast_id)

    def broadcast_update_file(message, broadcast_id):
        temp_data = load_temp_broadcast()
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
        else:
            bot.send_message(message.chat.id, "❌ Неверный тип файла. Попробуйте ещё раз или введите 'нет'/'не'.")
            return

        temp_data[broadcast_id] = draft
        save_temp_broadcast(temp_data)
        send_broadcast_preview(message.chat.id, broadcast_id, draft)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_edit_link"))
    def broadcast_edit_link(call):
        _, broadcast_id = call.data.split("|", 1)
        msg = bot.send_message(call.message.chat.id, "🔗 Введите новую ссылку (или 'нет'/'не' для удаления):")
        bot.register_next_step_handler(msg, broadcast_update_link, broadcast_id)

    def broadcast_update_link(message, broadcast_id):
        if message.content_type != "text":
            bot.send_message(message.chat.id, "❌ Это не текст. Попробуйте ещё раз.")
            bot.register_next_step_handler(message, broadcast_update_link, broadcast_id)
            return

        temp_data = load_temp_broadcast()
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

        # Сохраняем черновик в broadcasts.json
        broadcasts = load_broadcasts()
        broadcasts[broadcast_id] = temp_data[broadcast_id]
        save_broadcasts(broadcasts)

        # Удаляем из временных черновиков
        del temp_data[broadcast_id]
        save_temp_broadcast(temp_data)

        # Предлагаем сразу отправить или запланировать
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚀 Отправить сейчас", callback_data=f"broadcast_send_now|{broadcast_id}"))
        markup.add(InlineKeyboardButton("🕰 Указать время на завтра (МСК)", callback_data=f"broadcast_schedule|{broadcast_id}"))
        bot.send_message(call.message.chat.id, "✅ Черновик сохранён. Выберите действие:", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_send_now"))
    def broadcast_send_now(call):
        _, broadcast_id = call.data.split("|", 1)
        broadcasts = load_broadcasts()
        broadcast = broadcasts.get(broadcast_id)
        if not broadcast:
            bot.send_message(call.message.chat.id, "❌ Рассылка не найдена.")
            return

        # Отправляем прямо сейчас
        count = do_broadcast(bot, broadcast)
        bot.send_message(call.message.chat.id, f"✅ Рассылка отправлена {count} пользователям!")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_schedule"))
    def broadcast_schedule(call):
        _, broadcast_id = call.data.split("|", 1)
        msg = bot.send_message(call.message.chat.id, "🕰 Введите время на завтра в формате ЧЧ:ММ (МСК):")
        bot.register_next_step_handler(msg, broadcast_schedule_time, broadcast_id)

    def broadcast_schedule_time(message, broadcast_id):
        broadcasts = load_broadcasts()
        broadcast = broadcasts.get(broadcast_id)
        if not broadcast:
            bot.send_message(message.chat.id, "❌ Рассылка не найдена.")
            return

        time_str = message.text.strip()
        try:
            hours, minutes = map(int, time_str.split(":"))
        except:
            msg = bot.send_message(message.chat.id, "❌ Неверный формат. Попробуйте ещё раз (например: 15:30).")
            bot.register_next_step_handler(msg, broadcast_schedule_time, broadcast_id)
            return

        # Расчитываем завтрашнее время в МСК
        now_msk = datetime.now(MSK_TZ)
        tomorrow_msk = now_msk + timedelta(days=1)
        run_date = tomorrow_msk.replace(hour=hours, minute=minutes, second=0, microsecond=0)

        # Планируем через APScheduler
        job = scheduler.add_job(do_scheduled_broadcast, 'date', run_date=run_date, args=[bot, broadcast_id])

        # Сохраняем в scheduled_broadcasts.json
        scheduled = load_scheduled()
        scheduled.append({
            "job_id": job.id,
            "broadcast_id": broadcast_id,
            "run_date": str(run_date),
            "status": "scheduled"
        })
        save_scheduled(scheduled)

        bot.send_message(message.chat.id, f"📅 Рассылка запланирована на {run_date.strftime('%d.%m %H:%M')} (МСК).")

    # --------------------------------------
    # 4. Список запланированных рассылок (команда /запланированные)
    # --------------------------------------
    @bot.message_handler(commands=["запланированные"])
    def list_scheduled_broadcasts(message):
        if message.from_user.id != admin_id:
            return
        scheduled = load_scheduled()
        if not scheduled:
            bot.send_message(message.chat.id, "Нет запланированных рассылок.")
            return

        for item in scheduled:
            if item["status"] == "scheduled":
                bc_id = item["broadcast_id"]
                run_date = item["run_date"]
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("✏️ Редактировать", callback_data=f"scheduled_edit|{bc_id}|{item['job_id']}"))
                markup.add(InlineKeyboardButton("❌ Удалить", callback_data=f"scheduled_delete|{bc_id}|{item['job_id']}"))

                text = f"Рассылка ID: {bc_id}\nОтправка по МСК: {run_date}"
                bot.send_message(message.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("scheduled_delete"))
    def scheduled_delete(call):
        _, bc_id, job_id = call.data.split("|", 2)
        try:
            scheduler.remove_job(job_id)
        except:
            pass

        scheduled = load_scheduled()
        for item in scheduled:
            if item["job_id"] == job_id:
                item["status"] = "cancelled"
        save_scheduled(scheduled)

        bot.send_message(call.message.chat.id, f"🗑️ Запланированная рассылка {bc_id} удалена.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("scheduled_edit"))
    def scheduled_edit(call):
        _, bc_id, job_id = call.data.split("|", 2)
        try:
            scheduler.remove_job(job_id)
        except:
            pass

        scheduled = load_scheduled()
        for item in scheduled:
            if item["job_id"] == job_id:
                item["status"] = "editing"
        save_scheduled(scheduled)

        broadcasts = load_broadcasts()
        if bc_id not in broadcasts:
            bot.send_message(call.message.chat.id, "❌ Рассылка не найдена.")
            return

        # Переносим в temp_broadcasts.json, чтобы редактировать
        temp_data = load_temp_broadcast()
        temp_data[bc_id] = broadcasts[bc_id]
        save_temp_broadcast(temp_data)

        bot.send_message(call.message.chat.id, "🔁 Переводим рассылку в режим черновика. Теперь можете редактировать.")
        send_broadcast_preview(call.message.chat.id, bc_id, temp_data[bc_id])


def do_scheduled_broadcast(bot, broadcast_id):
    """Функция, которую вызывает APScheduler в заданное время."""
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
    """
    Реальная отправка рассылки пользователям. Возвращает кол-во получивших.
    """
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

