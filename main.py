import os
import json
import openpyxl
import pytz
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.background import BackgroundScheduler

from broadcast_handler import init_broadcast, do_scheduled_broadcast, restore_scheduled_jobs
from scenario_handler import init_scenarios

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

bot = __import__("telebot").TeleBot(BOT_TOKEN)
scheduler = BackgroundScheduler()
scheduler.start()

# Создаем необходимые файлы, если их нет
FILE_LIST = {
    "scenario_store.json": {},
    "user_db.json": [],
    "broadcasts.json": {},
    "scheduled_broadcasts.json": [],
    "temp_broadcasts.json": {}
}
for filename, default in FILE_LIST.items():
    if not os.path.exists(filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False)

# Функция обновления информации о последней активности пользователя
def update_user_activity(user):
    try:
        with open("user_db.json", "r", encoding="utf-8") as f:
            users = json.load(f)
    except Exception:
        users = []
    found = False
    for u in users:
        if u["id"] == user.id:
            u["last_active"] = datetime.utcnow().isoformat()
            found = True
            break
    if not found:
        # Добавляем пользователя, если есть username (или можно доработать логику)
        new_user = {
            "id": user.id,
            "first_name": getattr(user, "first_name", ""),
            "username": getattr(user, "username", ""),
            "phone": "",
            "last_active": datetime.utcnow().isoformat()
        }
        users.append(new_user)
    with open("user_db.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False)

# /start – приветствие
@bot.message_handler(commands=["start"])
def handle_start(message):
    update_user_activity(message.from_user)
    bot.send_message(message.chat.id, "Привет! Добро пожаловать в бот.")

# /ping – проверка работы
@bot.message_handler(commands=["ping"])
def handle_ping(message):
    update_user_activity(message.from_user)
    bot.send_message(message.chat.id, "✅ Бот работает!")

# /контакты – выгрузка контактов пользователей в Excel
@bot.message_handler(commands=["контакты"])
def handle_contacts(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        with open("user_db.json", "r", encoding="utf-8") as f:
            users = json.load(f)
    except:
        users = []
    if not users:
        bot.send_message(message.chat.id, "Пользователей пока нет.")
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Contacts"
    ws.append(["ID", "Имя", "Username", "Последняя активность"])
    for u in users:
        ws.append([u["id"], u.get("first_name", ""), u.get("username", ""), u.get("last_active", "")])
    wb.save("contacts.xlsx")
    with open("contacts.xlsx", "rb") as doc:
        bot.send_document(message.chat.id, doc, caption="📋 Контакты пользователей")

# /пользователи – вывод общего числа и числа активных (за 7 дней)
@bot.message_handler(commands=["пользователи"])
def handle_users(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        with open("user_db.json", "r", encoding="utf-8") as f:
            users = json.load(f)
    except:
        users = []
    total = len(users)
    active = 0
    now = datetime.utcnow()
    for u in users:
        if "last_active" in u:
            try:
                last = datetime.fromisoformat(u["last_active"])
                if (now - last).days < 7:
                    active += 1
            except:
                pass
    bot.send_message(message.chat.id, f"Всего пользователей: {total}\nАктивных (за 7 дней): {active}")

# /скачать_сценарии – отправка файла сценариев (JSON)
@bot.message_handler(commands=["скачать_сценарии"])
def download_scenarios(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        with open("scenario_store.json", "rb") as f:
            bot.send_document(message.chat.id, f, caption="Сценарии")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при отправке файла сценариев: {e}")

# /скачать_рассылки – отправка файла рассылок (JSON) с информацией о доставке
@bot.message_handler(commands=["скачать_рассылки"])
def download_broadcasts(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        with open("broadcasts.json", "rb") as f:
            bot.send_document(message.chat.id, f, caption="Рассылки")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при отправке файла рассылок: {e}")

# Еженедельная статистика – отправка статистики в чат администратора
def send_weekly_statistics():
    try:
        with open("user_db.json", "r", encoding="utf-8") as f:
            users = json.load(f)
    except:
        users = []
    total = len(users)
    now = datetime.utcnow()
    new_users = sum(1 for u in users if "last_active" in u and (now - datetime.fromisoformat(u["last_active"])).days < 7)
    stats_text = f"📊 Статистика за неделю:\nНовых пользователей: {new_users}\nОбщее количество пользователей: {total}"
    bot.send_message(ADMIN_ID, stats_text)

# Планируем еженедельную статистику (каждый понедельник в 09:00 UTC)
scheduler.add_job(send_weekly_statistics, 'cron', day_of_week='mon', hour=9, minute=0)

# Восстанавливаем запланированные рассылки при старте
restore_scheduled_jobs(scheduler, bot)

# Инициализируем обработчики рассылок и сценариев
init_broadcast(bot, ADMIN_ID, scheduler)
init_scenarios(bot, ADMIN_ID)

bot.polling(none_stop=True)

