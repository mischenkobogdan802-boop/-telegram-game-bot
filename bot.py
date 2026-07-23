import os
import random
import sqlite3
import asyncio
import time

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext


TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)

dp = Dispatcher(storage=MemoryStorage())

os.makedirs("/opt/render/project/src/data", exist_ok=True)

db = sqlite3.connect("/opt/render/project/src/data/bot.db")
cursor = db.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 1000
)
""")

db.commit()


# ===== СТАН ВВЕДЕННЯ СТАВКИ =====

class BetState(StatesGroup):
    waiting_bet = State()


# ===== ДАНІ СПІЛЬНОГО ПОЛЬОТУ =====

flight_active = False
multiplier = 1.0
crash_point = 0

bets = {}

flight_message_ids = []


# ===== МЕНЮ =====

def menu():

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="✈️ Політ",
                    callback_data="flight"
                )
            ],

            [
                InlineKeyboardButton(
                    text="⭐ Баланс",
                    callback_data="balance"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🎁 Бонус",
                    callback_data="bonus"
                )
            ],

            [
                InlineKeyboardButton(
                    text="👤 Профіль",
                    callback_data="profile"
                )
            ]

        ]
    )


# ===== START =====

@dp.message(CommandStart())
async def start(message: types.Message):

    user = message.from_user

    cursor.execute(
        "INSERT OR IGNORE INTO users(user_id, username) VALUES (?,?)",
        (user.id, user.username)
    )

    db.commit()


    await message.answer(
        "🎮 Ласкаво просимо!\n\n"
        "✈️ Гра: Crash Політ\n"
        "⭐ Баланс: 0 монет",
        reply_markup=menu()
    )


# ===== БАЛАНС =====

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
# ===== КНОПКА ПОЛІТ =====

@dp.callback_query(lambda c: c.data == "flight")
async def flight_start(callback: types.CallbackQuery, state: FSMContext):

    global flight_active

    if flight_active:
        await callback.answer(
            "✈️ Політ вже йде! Дочекайся наступного раунду.",
            show_alert=True
        )
        return

    await callback.message.answer(
        "✈️ Новий політ!\n\n"
        "Введи свою ставку:"
    )

    await state.set_state(BetState.waiting_bet)

    await callback.answer()


# ===== ОТРИМАННЯ СТАВКИ =====

@dp.message(BetState.waiting_bet)
async def get_bet(message: types.Message, state: FSMContext):

    global flight_active
    global multiplier
    global crash_point


    try:
        bet = int(message.text)

    except:

        await message.answer(
            "❌ Введи число"
        )

        return



    cursor.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (message.from_user.id,)
    )

    result = cursor.fetchone()


    if not result or result[0] < bet:

        await message.answer(
            "❌ Недостатньо монет"
        )

        await state.clear()
        return



    if bet <= 0:

        await message.answer(
            "❌ Ставка має бути більше 0"
        )

        return



    # списуємо ставку

    cursor.execute(
        "UPDATE users SET balance=balance-? WHERE user_id=?",
        (bet, message.from_user.id)
    )

    db.commit()



    bets[message.from_user.id] = {
        "bet": bet,
        "cashout": False
    }


    await state.clear()



    # якщо літак ще не запущений
    if not flight_active:

    flight_active = True

    multiplier = 1.0

    chance = random.randint(1, 100)

    if chance <= 70:
        crash_point = round(random.uniform(1.00, 1.50), 2)

    elif chance <= 95:
        crash_point = round(random.uniform(1.50, 3.00), 2)

    else:
        crash_point = round(random.uniform(3.00, 10.00), 2)

    await message.answer(
        "✈️ ЛІТАК ЗЛЕТІВ!\n\n"
        "Коефіцієнт: 1.00x"
    )

    asyncio.create_task(run_flight())

else:

    await message.answer(
        "✅ Ти приєднався до польоту!"
    )



# ===== АНІМАЦІЯ ПОЛЬОТУ =====


async def run_flight():

    global multiplier
    global flight_active


    while multiplier < crash_point:


        await asyncio.sleep(2)


        multiplier += 0.25

        multiplier = round(multiplier,2)


        text = (
            "✈️ Літак летить!\n\n"
            f"🚀 Коефіцієнт: {multiplier}x"
        )


        # повідомлення всім гравцям

        for user_id in bets:

            try:

                await bot.send_message(
                    user_id,
                    text,
                    reply_markup=cashout_button()
                )

            except:
                pass



    await crash()
    # ===== КНОПКА ЗАБРАТИ =====

def cashout_button():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💰 Забрати",
                    callback_data="cashout"
                )
            ]
        ]
    )



@dp.callback_query(lambda c: c.data == "cashout")
async def cashout(callback: types.CallbackQuery):

    user_id = callback.from_user.id


    if user_id not in bets:

        await callback.answer(
            "❌ У тебе немає ставки",
            show_alert=True
        )

        return



    if bets[user_id]["cashout"]:

        await callback.answer(
            "Ти вже забрав виграш",
            show_alert=True
        )

        return



    bets[user_id]["cashout"] = True


    bet = bets[user_id]["bet"]


    win = int(
        bet * multiplier
    )


    cursor.execute(
        "UPDATE users SET balance=balance+? WHERE user_id=?",
        (win, user_id)
    )

    db.commit()



    await callback.message.answer(
        "💰 Ти забрав виграш!\n\n"
        f"✈️ Коефіцієнт: {multiplier}x\n"
        f"⭐ Отримано: {win} монет"
    )


    await callback.answer()



# ===== ПАДІННЯ ЛІТАКА =====


async def crash():

    global flight_active
    global multiplier


    flight_active = False


    text = (
        "💥 ЛІТАК ВПАВ!\n\n"
        f"Останній коефіцієнт: {multiplier}x"
    )


    for user_id in bets:

        try:

            await bot.send_message(
                user_id,
                text
            )

        except:
            pass



    bets.clear()

    multiplier = 1.0




# ===== БОНУС =====


@dp.callback_query(lambda c: c.data == "bonus")
async def bonus(callback: types.CallbackQuery):

    user_id = callback.from_user.id

    now = int(time.time())


    cursor.execute(
        "SELECT last_bonus FROM users WHERE user_id=?",
        (user_id,)
    )

    result = cursor.fetchone()


    if result:

        last_bonus = result[0]

        # 24 години = 86400 секунд
        if now - last_bonus < 86400:

            left = 86400 - (now - last_bonus)

            hours = left // 3600
            minutes = (left % 3600) // 60


            await callback.answer(
                f"⏳ Бонус вже отриманий!\n"
                f"Повертайся через {hours} год {minutes} хв",
                show_alert=True
            )

            return



    bonus_amount = 10


    cursor.execute(
        "UPDATE users SET balance = balance + ?, last_bonus = ? WHERE user_id=?",
        (bonus_amount, now, user_id)
    )


    db.commit()


    await callback.message.edit_text(
        f"🎁 Ти отримав щоденний бонус +{bonus_amount} монет!",
        reply_markup=menu()
    )



# ===== ПРОФІЛЬ =====


@dp.callback_query(lambda c: c.data == "profile")
async def profile(callback: types.CallbackQuery):

    cursor.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (callback.from_user.id,)
    )

    result = cursor.fetchone()

    balance = result[0] if result else 0


    await callback.message.edit_text(
        f"👤 Профіль\n\n"
        f"🆔 ID: {callback.from_user.id}\n"
        f"⭐ Баланс: {balance}",
        reply_markup=menu()
    )



# ===== ЗАПУСК =====


async def main():

    await dp.start_polling(bot)



if __name__ == "__main__":

    asyncio.run(main())
