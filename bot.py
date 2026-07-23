import os
import random
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

db = sqlite3.connect("bot.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 1000
)
""")
db.commit()


def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Грати", callback_data="play")],
        [InlineKeyboardButton(text="🪙 Баланс", callback_data="balance")],
        [InlineKeyboardButton(text="🎁 Бонус", callback_data="bonus")],
        [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="rating")],
        [InlineKeyboardButton(text="👤 Профіль", callback_data="profile")]
    ])


@dp.message(CommandStart())
async def start(message: types.Message):
    user = message.from_user

    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user.id, user.username)
    )
    db.commit()

    await message.answer(
        f"👋 Привіт, {user.first_name}!\n\n"
        "🎮 Ласкаво просимо до нашої гри!\n"
        "🪙 Твій стартовий баланс: 1000 монет.",
        reply_markup=menu()
    )


@dp.callback_query(lambda c: c.data == "balance")
async def balance(callback: types.CallbackQuery):
    cursor.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (callback.from_user.id,)
    )
    result = cursor.fetchone()

    balance = result[0] if result else 0

    await callback.message.edit_text(
        f"🪙 Твій баланс: {balance} монет",
        reply_markup=menu()
    )


@dp.callback_query(lambda c: c.data == "play")
async def play(callback: types.CallbackQuery):
    cursor.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (callback.from_user.id,)
    )
    result = cursor.fetchone()

    if not result or result[0] < 10:
        await callback.answer(
            "❌ Потрібно мінімум 10 монет!",
            show_alert=True
        )
        return

    # Безпечна гра на віртуальні монети
    change = random.choice([-20, -10, 10, 20, 30])

    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (change, callback.from_user.id)
    )
    db.commit()

    if change > 0:
        text = f"🎉 Ти отримав +{change} монет!"
    else:
        text = f"😅 Ти втратив {abs(change)} монет."

    await callback.message.edit_text(
        text,
        reply_markup=menu()
    )


@dp.callback_query(lambda c: c.data == "bonus")
async def bonus(callback: types.CallbackQuery):
    bonus_amount = 100

    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (bonus_amount, callback.from_user.id)
    )
    db.commit()

    await callback.message.edit_text(
        f"🎁 Ти отримав бонус +{bonus_amount} монет!",
        reply_markup=menu()
    )


@dp.callback_query(lambda c: c.data == "profile")
async def profile(callback: types.CallbackQuery):
    user = callback.from_user

    cursor.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user.id,)
    )
    result = cursor.fetchone()

    balance = result[0] if result else 0

    await callback.message.edit_text(
        f"👤 Профіль\n\n"
        f"🆔 ID: {user.id}\n"
        f"👤 Ім'я: {user.first_name}\n"
        f"🪙 Баланс: {balance}",
        reply_markup=menu()
    )


@dp.callback_query(lambda c: c.data == "rating")
async def rating(callback: types.CallbackQuery):
    cursor.execute(
        "SELECT username, balance FROM users "
        "ORDER BY balance DESC LIMIT 10"
    )

    users = cursor.fetchall()

    text = "🏆 ТОП-10 ГРАВЦІВ\n\n"

    for i, (username, balance) in enumerate(users, 1):
        name = username or "Гравець"
        text += f"{i}. {name} — {balance} 🪙\n"

    await callback.message.edit_text(
        text,
        reply_markup=menu()
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
