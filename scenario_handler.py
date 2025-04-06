import json
import uuid
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

SCENARIO_FILE = "scenario_store.json"
TEMP_SCENARIO_FILE = "temp_scenarios.json"

def load_temp():
    try:
        with open(TEMP_SCENARIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_temp(data):
    with open(TEMP_SCENARIO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def init_scenarios(bot, admin_id):
    @bot.message_handler(commands=["сценарий"])
    def handle_scenario(message):
        if message.from_user.id != admin_id:
            return
        bot.send_message(message.chat.id, "📝 Введите текст сценария:")
        bot.register_next_step_handler(message, get_scenario_text)
    
    def get_scenario_text(message):
        text = message.text
        scenario_id = str(uuid.uuid4())
        temp_data = load_temp()
        temp_data[scenario_id] = {"text": text, "file_id": None, "file_type": None, "link": ""}
        save_temp(temp_data)
        bot.send_message(message.chat.id, "📎 Прикрепите файл (или введите 'нет'/'не'):")
        bot.register_next_step_handler(message, get_scenario_file, scenario_id)
    
    def get_scenario_file(message, scenario_id):
        temp_data = load_temp()
        if scenario_id not in temp_data:
            bot.send_message(message.chat.id, "❌ Черновик сценария не найден.")
            return
        draft = temp_data[scenario_id]
        if message.text and message.text.lower() in ["нет", "не"]:
            pass
        elif message.document:
            draft["file_id"] = message.document.file_id
            draft["file_type"] = "document"
        elif message.audio:
            draft["file_id"] = message.audio.file_id
            draft["file_type"] = "audio"
        elif message.video:
            draft["file_id"] = message.video.file_id
            draft["file_type"] = "video"
        elif message.photo:
            draft["file_id"] = message.photo[-1].file_id
            draft["file_type"] = "photo"
        else:
            bot.send_message(message.chat.id, "❌ Неверный тип файла. Попробуйте ещё раз или введите 'нет'/'не'.")
            return
        temp_data[scenario_id] = draft
        save_temp(temp_data)
        bot.send_message(message.chat.id, "🔗 Введите ссылку (или 'нет'/'не' для пропуска):")
        bot.register_next_step_handler(message, preview_scenario, scenario_id)
    
    def preview_scenario(message, scenario_id):
        if message.content_type != "text":
            bot.send_message(message.chat.id, "❌ Это не текст. Попробуйте ещё раз.")
            bot.register_next_step_handler(message, preview_scenario, scenario_id)
            return
        link = message.text.strip()
        if link.lower() in ["нет", "не"]:
            link = ""
        temp_data = load_temp()
        if scenario_id not in temp_data:
            bot.send_message(message.chat.id, "❌ Черновик сценария не найден.")
            return
        temp_data[scenario_id]["link"] = link
        save_temp(temp_data)
        send_scenario_preview(bot, message.chat.id, scenario_id, temp_data[scenario_id])
    
    def send_scenario_preview(bot, chat_id, scenario_id, draft):
        text = draft["text"]
        link = draft.get("link", "")
        file_id = draft.get("file_id")
        file_type = draft.get("file_type")
        preview = f"📘 <b>Предпросмотр сценария:</b>\n\n{text}"
        if link:
            preview += f"\n\n🔗 <a href='{link}'>{link}</a>"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✏️ Изменить текст", callback_data=f"scenario_edit_text|{scenario_id}"))
        markup.add(InlineKeyboardButton("✏️ Изменить файл", callback_data=f"scenario_edit_file|{scenario_id}"))
        markup.add(InlineKeyboardButton("✏️ Изменить ссылку", callback_data=f"scenario_edit_link|{scenario_id}"))
        markup.add(InlineKeyboardButton("✅ Сохранить", callback_data=f"save_сценарий|{scenario_id}"))
        markup.add(InlineKeyboardButton("❌ Удалить", callback_data=f"delete_sценарий|{scenario_id}"))
        try:
            if file_id:
                if file_type == "photo":
                    bot.send_photo(chat_id, file_id, caption=preview, parse_mode="HTML", reply_markup=markup)
                elif file_type == "video":
                    bot.send_video(chat_id, file_id, caption=preview, parse_mode="HTML", reply_markup=markup)
                elif file_type == "audio":
                    bot.send_audio(chat_id, file_id, caption=preview, parse_mode="HTML", reply_markup=markup)
                else:
                    bot.send_document(chat_id, file_id, caption=preview, parse_mode="HTML", reply_markup=markup)
            else:
                bot.send_message(chat_id, preview, parse_mode="HTML", reply_markup=markup)
        except Exception:
            bot.send_message(chat_id, preview, parse_mode="HTML", reply_markup=markup)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("scenario_edit_text"))
    def scenario_edit_text(call):
        _, scenario_id = call.data.split("|", 1)
        msg = bot.send_message(call.message.chat.id, "✏️ Введите новый текст сценария:")
        bot.register_next_step_handler(msg, scenario_update_text, scenario_id)
    
    def scenario_update_text(message, scenario_id):
        temp_data = load_temp()
        if scenario_id not in temp_data:
            bot.send_message(message.chat.id, "❌ Черновик сценария не найден.")
            return
        temp_data[scenario_id]["text"] = message.text
        save_temp(temp_data)
        send_scenario_preview(bot, message.chat.id, scenario_id, temp_data[scenario_id])
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("scenario_edit_file"))
    def scenario_edit_file(call):
        _, scenario_id = call.data.split("|", 1)
        msg = bot.send_message(call.message.chat.id, "📎 Прикрепите новый файл (или введите 'нет'/'не' для удаления):")
        bot.register_next_step_handler(msg, scenario_update_file, scenario_id)
    
    def scenario_update_file(message, scenario_id):
        temp_data = load_temp()
        if scenario_id not in temp_data:
            bot.send_message(message.chat.id, "❌ Черновик сценария не найден.")
            return
        draft = temp_data[scenario_id]
        if message.text and message.text.lower() in ["нет", "не"]:
            draft["file_id"] = None
            draft["file_type"] = None
        elif message.document:
            draft["file_id"] = message.document.file_id
            draft["file_type"] = "document"
        elif message.audio:
            draft["file_id"] = message.audio.file_id
            draft["file_type"] = "audio"
        elif message.video:
            draft["file_id"] = message.video.file_id
            draft["file_type"] = "video"
        elif message.photo:
            draft["file_id"] = message.photo[-1].file_id
            draft["file_type"] = "photo"
        else:
            bot.send_message(message.chat.id, "❌ Неверный тип файла. Попробуйте ещё раз или введите 'нет'/'не'.")
            return
        temp_data[scenario_id] = draft
        save_temp(temp_data)
        send_scenario_preview(bot, call.message.chat.id, scenario_id, draft)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("scenario_edit_link"))
    def scenario_edit_link(call):
        _, scenario_id = call.data.split("|", 1)
        msg = bot.send_message(call.message.chat.id, "🔗 Введите новую ссылку (или введите 'нет'/'не' для удаления):")
        bot.register_next_step_handler(msg, scenario_update_link, scenario_id)
    
    def scenario_update_link(message, scenario_id):
        if message.content_type != "text":
            bot.send_message(message.chat.id, "❌ Это не текст. Попробуйте ещё раз.")
            bot.register_next_step_handler(message, scenario_update_link, scenario_id)
            return
        link_text = message.text.strip()
        if link_text.lower() in ["нет", "не"]:
            link_text = ""
        temp_data = load_temp()
        if scenario_id not in temp_data:
            bot.send_message(message.chat.id, "❌ Черновик сценария не найден.")
            return
        temp_data[scenario_id]["link"] = link_text
        save_temp(temp_data)
        send_scenario_preview(bot, message.chat.id, scenario_id, temp_data[scenario_id])
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("save_сценарий"))
    def save_scenario(call):
        _, scenario_id = call.data.split("|", 1)
        temp_data = load_temp()
        data = temp_data.get(scenario_id)
        if not data:
            bot.send_message(call.message.chat.id, "❌ Ошибка: данные не найдены.")
            return
        msg = bot.send_message(call.message.chat.id, "💬 Введите короткий код для сценария (латиницей):")
        bot.register_next_step_handler(msg, save_final, data, scenario_id)
    
    def save_final(message, data, scenario_id):
        code = message.text.strip()
        try:
            with open(SCENARIO_FILE, "r", encoding="utf-8") as f:
                scenarios = json.load(f)
        except:
            scenarios = {}
        scenarios[code] = data
        with open(SCENARIO_FILE, "w", encoding="utf-8") as f:
            json.dump(scenarios, f, ensure_ascii=False)
        temp_data = load_temp()
        if scenario_id in temp_data:
            del temp_data[scenario_id]
            save_temp(temp_data)
        bot.send_message(message.chat.id, f"✅ Сценарий сохранён!\nСсылка: t.me/{bot.get_me().username}?start={code}")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("delete_sценарий"))
    def delete_scenario(call):
        _, scenario_id = call.data.split("|", 1)
        temp_data = load_temp()
        if scenario_id in temp_data:
            del temp_data[scenario_id]
            save_temp(temp_data)
            bot.send_message(call.message.chat.id, "🗑️ Черновик удалён.")
        else:
            bot.send_message(call.message.chat.id, "❌ Черновик не найден.")


