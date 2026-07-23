import os
import random
import sqlite3
import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


TOKEN = os.getenv("BOT_TOKEN")

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
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✈️ Політ",
                callback_data="flight"
            )],

            [InlineKeyboardButton(
                text="⭐️ Баланс",
                callback_data="balance"
            )],

            [InlineKeyboardButton(
                text="🎁 Бонус",
                callback_data="bonus"
            )],

            [InlineKeyboardButton(
                text="🏆 Рейтинг",
                callback_data="rating"
            )],

            [InlineKeyboardButton(
                text="👤 Профіль",
                callback_data="profile"
            )]
        ]
    )


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
        "🎮 Гра запущена!\n"
        "⭐ Твій баланс: 1000 монет",
        reply_markup=menu()
    )


@dp.callback_query(lambda c: c.data == "balance")
async def balance(callback: types.CallbackQuery):

    cursor.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (callback.from_user.id,)
    )

    result = cursor.fetchone()

    coins = result[0] if result else 0


    await callback.message.edit_text(
        f"⭐ Твій баланс: {coins} монет",
        reply_markup=menu()
    )


@dp.callback_query(lambda c: c.data == "flight")
async def flight(callback: types.CallbackQuery):

    cursor.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (callback.from_user.id,)
    )

    result = cursor.fetchone()


    if not result:
        await callback.answer(
            "Натисни /start",
            show_alert=True
        )
        return


    balance = result[0]


    if balance < 10:

        await callback.answer(
            "❌ Потрібно 10 монет!",
            show_alert=True
        )

        return


    chance = random.randint(1,100)


    if chance <= 50:

        win = random.randint(10,50)


        cursor.execute(
            "UPDATE users SET balance=balance+? WHERE user_id=?",
            (win, callback.from_user.id)
        )


        text = (
            "✈️ Політ успішний!\n\n"
            f"🎉 +{win} монет"
        )


    else:

        cursor.execute(
            "UPDATE users SET balance=balance-10 WHERE user_id=?",
            (callback.from_user.id,)
        )


        text = (
            "✈️ Політ невдалий 😢\n\n"
            "💸 -10 монет"
        )


    db.commit()


    await callback.message.edit_text(
        text,
        reply_markup=menu()
    )


    await callback.answer()
    @dp.callback_query(lambda c: c.data == "bonus")
async def bonus(callback: types.CallbackQuery):

    bonus_amount = 5

    cursor.execute(
        "UPDATE users SET balance=balance+? WHERE user_id=?",
        (bonus_amount, callback.from_user.id)
    )

    db.commit()


    await callback.message.edit_text(
        f"🎁 Ти отримав +{bonus_amount} монет!",
        reply_markup=menu()
    )


@dp.callback_query(lambda c: c.data == "profile")
async def profile(callback: types.CallbackQuery):

    user = callback.from_user


    cursor.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (user.id,)
    )

    result = cursor.fetchone()

    balance = result[0] if result else 0


    await callback.message.edit_text(
        f"👤 Профіль\n\n"
        f"🆔 ID: {user.id}\n"
        f"👤 Ім'я: {user.first_name}\n"
        f"⭐ Баланс: {balance}",
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

        text += (
            f"{i}. {name} — "
            f"{balance} ⭐\n"
        )


    await callback.message.edit_text(
        text,
        reply_markup=menu()
    )


async def main():

    await dp.start_polling(bot)



if __name__ == "__main__":
    asyncio.run(main())
