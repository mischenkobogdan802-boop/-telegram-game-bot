import asyncio
import random

from aiogram import Bot
from keyboards import cashout_keyboard
from database import add_balance, remove_balance, get_balance

# ===========================
# ГЛОБАЛЬНІ ЗМІННІ
# ===========================

flight_active = False
multiplier = 1.00
crash_point = 1.00

# Ставки поточного раунду
bets = {}

# Повідомлення польоту
flight_messages = {}

# Ставки наступного раунду
next_round_bets = {}
def generate_crash():

    chance = random.randint(1, 100)

    if chance <= 70:
        return round(random.uniform(1.00, 1.50), 2)

    elif chance <= 95:
        return round(random.uniform(1.50, 3.00), 2)

    else:
        return round(random.uniform(3.00, 10.00), 2)
      async def add_bet(user_id: int, amount: int):

    global bets
    global next_round_bets
    global flight_active

    if get_balance(user_id) < amount:
        return False

    remove_balance(user_id, amount)

    if flight_active:

        next_round_bets[user_id] = {
            "bet": amount,
            "cashout": False
        }

    else:

        bets[user_id] = {
            "bet": amount,
            "cashout": False
        }

    return True
async def start_round(bot: Bot):

    global flight_active
    global multiplier
    global crash_point

    if flight_active:
        return

    if not bets:
        return

    flight_active = True
    multiplier = 1.00
    crash_point = generate_crash()

    flight_messages.clear()

    for user_id in bets:

        try:

            msg = await bot.send_message(
                chat_id=user_id,
                text="✈️ Літак злетів!\n\n🚀 1.00x",
                reply_markup=cashout_keyboard()
            )

            flight_messages[user_id] = msg.message_id

        except:
            pass

    asyncio.create_task(run_round(bot))
async def run_round(bot: Bot):

    global multiplier

    while multiplier < crash_point:

        await asyncio.sleep(2)

        multiplier = round(multiplier + 0.25, 2)

        text = (
            "✈️ Політ\n\n"
            f"🚀 Коефіцієнт: {multiplier}x"
        )

        for user_id in list(flight_messages.keys()):

            try:

                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=flight_messages[user_id],
                    text=text,
                    reply_markup=cashout_keyboard()
                )

            except:
                pass

    await finish_round(bot)
async def finish_round(bot: Bot):

    global flight_active
    global multiplier
    global bets
    global next_round_bets

    text = (
        "💥 ЛІТАК ВПАВ!\n\n"
        f"Коефіцієнт: {multiplier}x"
    )

    for user_id in list(flight_messages.keys()):

        try:

            await bot.edit_message_text(
                chat_id=user_id,
                message_id=flight_messages[user_id],
                text=text
            )

        except:
            pass

    flight_messages.clear()

    bets = next_round_bets.copy()
    next_round_bets.clear()

    multiplier = 1.00
    flight_active = False

    await asyncio.sleep(8)

    if bets:

        asyncio.create_task(
            start_round(bot)
        )
      async def cashout(user_id: int):

    global bets
    global multiplier

    if user_id not in bets:
        return None

    if bets[user_id]["cashout"]:
        return None

    bets[user_id]["cashout"] = True

    bet = bets[user_id]["bet"]

    win = int(
        bet * multiplier
    )

    add_balance(
        user_id,
        win
    )

    return win

def player_exists(user_id):

    return user_id in bets
