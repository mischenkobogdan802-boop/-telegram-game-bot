import os
import asyncio
import logging
import sqlite3
import time
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command

# Отримуємо токен з налаштувань Render
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== 1. БАЗА ДАНИХ ====================
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    # Створюємо таблицю. Баланс за замовчуванням = 0
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            last_bonus INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id: int, username: str):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance, last_bonus FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    # Якщо користувача немає, створюємо з балансом 0
    if not row:
        cursor.execute("INSERT INTO users (user_id, username, balance, last_bonus) VALUES (?, ?, 0, 0)", (user_id, username))
        conn.commit()
        row = (user_id, username, 0, 0)
    conn.close()
    return row

def update_balance(user_id: int, delta: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (delta, user_id))
    conn.commit()
    conn.close()

# ==================== 2. КОМАНДИ БОТА ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    get_user(message.from_user.id, message.from_user.username or "Гравець")
    await message.answer(
        "👋 **Привіт! Це Crash Game.**\n\n"
        "Твій початковий баланс: 0 ⭐\n"
        "Щоб почати, візьми щоденний бонус!\n\n"
        "Команди:\n"
        "🔹 /profile — Мій баланс\n"
        "🔹 /bonus — Отримати 5 ⭐ (раз на 24 год)",
        parse_mode="Markdown"
    )

@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    user = get_user(message.from_user.id, message.from_user.username or "Гравець")
    await message.answer(
        f"👤 **Профіль:** {user[1]}\n"
        f"💰 **Баланс:** `{user[2]}` ⭐",
        parse_mode="Markdown"
    )

@dp.message(Command("bonus"))
async def cmd_bonus(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.username or "Гравець")
    
    now = int(time.time())
    last_bonus = user[3]
    
    # 86400 секунд = 24 години
    if now - last_bonus >= 86400:
        update_balance(user_id, 5) # Даємо 5 зірок
        
        # Оновлюємо час останнього бонусу
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now, user_id))
        conn.commit()
        conn.close()
        
        await message.answer("🎁 Ви успішно отримали щоденний бонус: **+5 ⭐**!")
    else:
        remaining = 86400 - (now - last_bonus)
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await message.answer(f"⏳ Бонус недоступний. Повертайтесь через **{hours} год {minutes} хв**.")

# ==================== 3. ЗАПУСК ====================
async def main():
    init_db()
    print("Бот запущено. База даних готова.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
