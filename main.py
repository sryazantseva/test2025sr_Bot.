# main.py
# Telegram бот: рассылки, сценарии, автоопределение часового пояса, экспорт, поддержка всех типов медиа

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import sqlite3
import pytz
import datetime
import os
import pandas as pd
import re

TOKEN = 'YOUR_TOKEN_HERE'
TZ = pytz.timezone("Europe/Moscow")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
scheduler = AsyncIOScheduler(timezone=TZ)
scheduler.start()

# --- Состояния FSM ---
class BroadcastState(StatesGroup):
    waiting_for_media = State()
    waiting_for_caption = State()
    waiting_for_time = State()

class ScenarioState(StatesGroup):
    collecting = State()
    confirming = State()

# --- DB Init ---
conn = sqlite3.connect("bot.db")
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT, phone TEXT, created_at TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS broadcasts
             (id INTEGER PRIMARY KEY AUTOINCREMENT, media_type TEXT, file_id TEXT, caption TEXT, time TEXT, status TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS scenarios
             (id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id INTEGER, steps TEXT, created_at TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS scenario_access
             (user_id INTEGER, scenario_id INTEGER, UNIQUE(user_id, scenario_id))''')
conn.commit()

# --- Команда для создания сценария ---
@dp.message_handler(commands=['сценарий_создать'])
async def create_scenario(message: types.Message, state: FSMContext):
    await state.update_data(steps=[])
    await message.answer("Вводите шаги сценария по одному. Когда закончите — /сценарий_сохранить. Для отмены — /отмена. Для просмотра — /сценарий_просмотр")
    await ScenarioState.collecting.set()

@dp.message_handler(commands=['сценарий_просмотр'], state=ScenarioState.collecting)
async def preview_scenario(message: types.Message, state: FSMContext):
    data = await state.get_data()
    steps = data.get("steps", [])
    if not steps:
        await message.answer("Пока что нет шагов.")
        return
    text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(steps)])
    kb = InlineKeyboardMarkup(row_width=2)
    for i in range(len(steps)):
        kb.insert(InlineKeyboardButton(f"❌ {i+1}", callback_data=f"delete_step_{i}"))
    kb.add(InlineKeyboardButton("🗑 Очистить всё", callback_data="clear_steps"))
    await message.answer(f"Ваши шаги:\n{text}", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("delete_step_"), state=ScenarioState.collecting)
async def delete_step(call: types.CallbackQuery, state: FSMContext):
    index = int(call.data.split("_")[-1])
    data = await state.get_data()
    steps = data.get("steps", [])
    if 0 <= index < len(steps):
        steps.pop(index)
        await state.update_data(steps=steps)
    await call.message.delete()
    await preview_scenario(call.message, state)

@dp.callback_query_handler(lambda c: c.data == "clear_steps", state=ScenarioState.collecting)
async def clear_steps(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(steps=[])
    await call.message.edit_text("Все шаги удалены.")

@dp.message_handler(commands=['отмена'], state=ScenarioState.collecting)
async def cancel_scenario(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Создание сценария отменено.")

@dp.message_handler(commands=['сценарий_сохранить'], state=ScenarioState.collecting)
async def save_scenario(message: types.Message, state: FSMContext):
    data = await state.get_data()
    steps = data.get("steps", [])
    if not steps:
        await message.answer("Вы не добавили ни одного шага.")
        return
    steps_text = "|||".join(steps)
    c.execute("INSERT INTO scenarios (creator_id, steps, created_at) VALUES (?, ?, ?)",
              (message.from_user.id, steps_text, datetime.datetime.now().isoformat()))
    conn.commit()
    scenario_id = c.lastrowid
    await message.answer(f"Сценарий сохранён. Ссылка на запуск: /сценарий?id={scenario_id}")
    await state.finish()

@dp.message_handler(state=ScenarioState.collecting)
async def collect_step(message: types.Message, state: FSMContext):
    data = await state.get_data()
    steps = data.get("steps", [])
    steps.append(message.text)
    await state.update_data(steps=steps)
    await message.answer(f"Шаг добавлен. Всего шагов: {len(steps)}")
