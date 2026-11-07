import sqlite3
import time
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "ТВІЙ_ТОКЕН_БОТА"  # Заміни на свій токен від BotFather
WEBAPP_URL = "https://ТВІЙ_ЛОГІН.github.io/ТВІЙ_РЕПОЗИТОРІЙ/" # Посилання на твій GitHub Pages

bot = Bot(token=TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT 0,
            joined_date INTEGER
        )
    """)
    conn.commit()
    conn.close()

init_db()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Гравець"
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, balance, wins, referrals, referred_by, joined_date) VALUES (?, ?, 0, 0, 0, 0, ?)", 
                       (user_id, username, int(time.time())))
        conn.commit()
    conn.close()

    # Тільки одна кнопка відкриття WebApp. Жодних інших кнопок чи меню немає!
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Відкрити Казино WebApp", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])

    await message.answer(
        "👋 Вітаємо у Telegram Казино!\n\n"
        "Натисніть кнопку нижче, щоб відкрити ігрову платформу:",
        reply_markup=keyboard
    )

# Синхронізація балансу із Mini App
@dp.message(F.web_app_data)
async def web_app_data_handler(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        new_balance = data.get("new_balance")
        if new_balance is not None:
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, message.from_user.id))
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"Помилка синхронізації: {e}")

if __name__ == "__main__":
    print("Бот запущено...")
    dp.run_polling(bot)
