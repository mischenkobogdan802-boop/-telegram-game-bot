import sqlite3
import time
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "ТВІЙ_ТОКЕН_БОТА"  # Заміни на свій токен від BotFather
ADMIN_ID = 7842251789
WEBAPP_URL = "https://ТВІЙ_ЛОГІН.github.io/ТВІЙ_РЕПОЗИТОРІЙ/" # Посилання на GitHub Pages

bot = Bot(token=TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    # Змінюємо DEFAULT 100 на DEFAULT 0 для нових таблиць
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            last_bonus INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT 0,
            joined_date INTEGER,
            rakeback INTEGER DEFAULT 0,
            max_win INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_user(user_id: int, username: str, referrer_id: int = 0):
    safe_username = username if username else "Гравець"
    now = int(time.time())
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance, last_bonus, wins, referrals, referred_by, joined_date, rakeback, max_win FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        valid_referrer = 0
        if referrer_id and referrer_id != user_id:
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (referrer_id,))
            if cursor.fetchone():
                valid_referrer = referrer_id
                cursor.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = ?", (referrer_id,))

        # Жорстко ставимо 0 для нових користувачів
        cursor.execute("""
            INSERT INTO users (user_id, username, balance, last_bonus, wins, referrals, referred_by, joined_date, rakeback, max_win) 
            VALUES (?, ?, 0, 0, 0, 0, ?, ?, 0, 0)
        """, (user_id, safe_username, valid_referrer, now))
        conn.commit()
        
        cursor.execute("SELECT user_id, username, balance, last_bonus, wins, referrals, referred_by, joined_date, rakeback, max_win FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
    conn.close()
    return row

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    args = message.text.split()
    referrer_id = 0
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].replace("ref_", ""))
        except ValueError:
            pass

    get_user(message.from_user.id, message.from_user.username, referrer_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Відкрити WebApp Casino", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="👤 Профіль", callback_data="profile"), InlineKeyboardButton(text="🏆 Топ", callback_data="top")]
    ])

    await message.answer(
        "👋 Вітаємо у преміальному Telegram Casino!\n\n"
        "Грайте у Ракеточку, Міни, Плінко та відкривайте кейси прямо у застосунку.",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "profile")
async def cb_profile(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id, callback.from_user.username)
    await callback.message.answer(
        f"👤 Профіль: @{user[1]}\n"
        f"🆔 ID: {user[0]}\n"
        f"💰 Баланс: {user[2]} ⭐\n"
        f"🏆 Перемог: {user[4]}\n"
        f"🤝 Рефералів: {user[5]}"
    )
    await callback.answer()

@dp.callback_query(F.data == "top")
async def cb_top(callback: types.CallbackQuery):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 5")
    rows = cursor.fetchall()
    conn.close()

    text = "🏆 **Топ гравців казино:**\n\n"
    for idx, row in enumerate(rows, 1):
        text += f"{idx}. @{row[0]} — {row[1]} ⭐\n"

    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

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
        print(f"Помилка синхронізації балансу: {e}")

if __name__ == "__main__":
    print("Бот запущено...")
    dp.run_polling(bot)
