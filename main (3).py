import telebot
import os
import json
import openpyxl
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# APScheduler
from apscheduler.schedulers.background import BackgroundScheduler

from broadcast_handler import init_broadcast, load_scheduled, save_scheduled, do_scheduled_broadcast
from scenario_handler import init_scenarios

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

bot = telebot.TeleBot(BOT_TOKEN)

SCENARIO_FILE = "scenario_store.json"
USER_FILE = "user_db.json"
BROADCAST_FILE = "broadcasts.json"
SCHEDULED_BROADCAST_FILE = "scheduled_broadcasts.json"

for file in [SCENARIO_FILE, USER_FILE, BROADCAST_FILE, SCHEDULED_BROADCAST_FILE]:
    if not os.path.exists(file):
        with open(file, "w", encoding="utf-8") as f:
            if file == USER_FILE:
                json.dump([], f)
            elif file == SCHEDULED_BROADCAST_FILE:
                json.dump([], f)
            else:
                json.dump({}, f)

# Инициализация APScheduler
scheduler = BackgroundScheduler()
scheduler.start()

# При старте загружаем все "scheduled_broadcasts.json" и восстанавливаем задачи
scheduled_list = load_scheduled()
for item in scheduled_list:
    if item["status"] == "scheduled":
        job_id = item["job_id"]
        broadcast_id = item["broadcast_id"]
        run_date_str = item["run_date"]
        try:
            run_date = datetime.fromisoformat(run_date_str)
            scheduler.add_job(
                do_scheduled_broadcast,
                'date',
                run_date=run_date,
                args=[bot, broadcast_id],
                id=job_id
            )
        except Exception as e:
            print(f"Не удалось восстановить задачу {broadcast_id}: {e}")

def save_user(user):
    with open(USER_FILE, "r", encoding="utf-8") as f:
        users = json.load(f)

    user_data = {
        "id": user.id,
        "first_name": getattr(user, "first_name", ""),
        "username": getattr(user, "username", ""),
        "phone": ""
    }
    # Сохраняем только если есть username или phone
    if not user_data["phone"] and not user_data["username"]:
        return

    if user.id not in [u["id"] for u in users]:
        users.append(user_data)
        with open(USER_FILE, "w", encoding="utf-8") as fw:
            json.dump(users, fw, ensure_ascii=False)

@bot.message_handler(commands=["start"])
def handle_start(message):
    save_user(message.from_user)
    args = message.text.split()
    if len(args) > 1:
        scenario_code = args[1]
        with open(SCENARIO_FILE, "r", encoding="utf-8") as f:
            scenarios = json.load(f)
        scenario = scenarios.get(scenario_code)
        if scenario:
            send_content(message.chat.id, scenario["text"], scenario.get("file_id"), scenario.get("file_or_link"))
        else:
            bot.send_message(message.chat.id, "❌ Такой сценарий не найден.")
    else:
        bot.send_message(message.chat.id, "Привет! Я бот Академии 🌿 Напиши /ping для проверки.")

@bot.message_handler(commands=["ping"])
def handle_ping(message):
    bot.send_message(message.chat.id, "✅ Бот работает!")

@bot.message_handler(commands=["контакты"])
def handle_download_users(message):
    if message.from_user.id != ADMIN_ID:
        return
    with open(USER_FILE, "r", encoding="utf-8") as f:
        users = json.load(f)
    if not users:
        bot.send_message(message.chat.id, "Пользователей пока нет.")
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Contacts"
    ws.append(["ID", "Имя", "Контакт"])

    for u in users:
        contact = u.get("phone") if u.get("phone") else u.get("username")
        if contact:
            ws.append([u["id"], u.get("first_name", ""), contact])

    wb.save("contacts.xlsx")
    bot.send_document(message.chat.id, open("contacts.xlsx", "rb"), caption="📋 Контакты пользователей")

@bot.message_handler(commands=["пользователи"])
def handle_users(message):
    if message.from_user.id != ADMIN_ID:
        return
    with open(USER_FILE, "r", encoding="utf-8") as f:
        users = json.load(f)
    bot.send_message(message.chat.id, f"Всего уникальных пользователей: {len(users)}")

def send_content(chat_id, text, file_id=None, link=None):
    final_text = text
    if link:
        final_text += f"\n\n🔗 {link}"
    if file_id:
        bot.send_document(chat_id, file_id, caption=final_text)
    else:
        bot.send_message(chat_id, final_text)

init_broadcast(bot, ADMIN_ID, scheduler)
init_scenarios(bot, ADMIN_ID)

print("BOT_TOKEN =", BOT_TOKEN)
print("ADMIN_ID =", ADMIN_ID)

# ... остальные импорты и настройки
print("Удаляем webhook...")
bot.remove_webhook()  # это удаляет любой ранее установленный webhook
print("Webhook удалён, начинаем polling...")
bot.polling()

