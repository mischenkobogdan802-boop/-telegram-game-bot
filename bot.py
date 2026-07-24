import os
import asyncio
import logging
import random
import sqlite3
import time
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton,
    LabeledPrice, PreCheckoutQuery
)
from aiogram.exceptions import TelegramBadRequest

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Стан для очікування кастомної ставки від користувача
class GameStates(StatesGroup):
    waiting_for_custom_bet = State()

# ==================== 1. БАЗА ДАНИХ (SQLite) ====================
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            last_bonus INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            user_id INTEGER PRIMARY KEY,
            amount INTEGER
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id: int, username: str):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance, last_bonus FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
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

# ==================== 2. СТАН ГРИ (CRASH) ====================
class CrashGame:
    def __init__(self):
        self.is_running = False
        self.current_multiplier = 1.00
        self.crashed = False
        self.target_multiplier = 1.00
        self.bets = {}  # user_id: {"amount": int, "username": str, "won": bool}
        self.live_messages = {}  # chat_id: message_id

    def generate_crash_multiplier(self) -> float:
        rand = random.random()
        if rand < 0.70:
            return round(random.uniform(1.00, 1.50), 2)
        elif rand < 0.95:
            return round(random.uniform(1.50, 4.00), 2)
        else:
            return round(random.uniform(4.00, 50.00), 2)

game = CrashGame()

async def update_live_messages(text: str, reply_markup=None):
    for chat_id, msg_id in list(game.live_messages.items()):
        try:
            await bot.edit_message_text(
                text, 
                chat_id=chat_id, 
                message_id=msg_id, 
                reply_markup=reply_markup, 
                parse_mode="Markdown"
            )
        except TelegramBadRequest:
            pass
        except Exception:
            pass

# ==================== 3. АВТОМАТИЧНИЙ ЦИКЛ ПОЛЬОТУ (20 сек) ====================
async def crash_game_loop():
    while True:
        # --- ФАЗА 1: Очікування ставок (10 секунд) ---
        game.is_running = False
        game.crashed = False
        game.bets.clear()

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bets")
        conn.commit()
        conn.close()

        kb_bet = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💵 1 ⭐", callback_data="bet_1"),
             InlineKeyboardButton(text="💵 5 ⭐", callback_data="bet_5"),
             InlineKeyboardButton(text="💵 10 ⭐", callback_data="bet_10")],
            [InlineKeyboardButton(text="✍️ Своя ставка", callback_data="custom_bet")]
        ])

        for countdown in range(10, 0, -2):
            text_wait = (
                f"⏳ **ЛІТАК НА ЗАПРАВЦІ!**\n\n"
                f"🚀 Зліт через: **{countdown} сек.**\n"
                f"Оберіть або введіть вашу ставку 👇"
            )
            await update_live_messages(text_wait, kb_bet)
            await asyncio.sleep(2)

        # --- ФАЗА 2: Початок польоту ---
        game.is_running = True
        game.target_multiplier = game.generate_crash_multiplier()
        game.current_multiplier = 1.00

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT b.user_id, b.amount, u.username FROM bets b JOIN users u ON b.user_id = u.user_id")
        current_bets = cursor.fetchall()
        conn.close()

        for u_id, amt, u_name in current_bets:
            game.bets[u_id] = {"amount": amt, "username": u_name, "won": False}

        kb_fly = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 ЗАБРАТИ ВИГРАШ", callback_data="cashout")]
        ])

        # --- ФАЗА 3: Анімація польоту ---
        step = 0.08
        while game.current_multiplier < game.target_multiplier:
            text_fly = (
                f"✈️ **ЛІТАК У ПОЛЬОТІ!**\n\n"
                f"📈 Поточний X: **{game.current_multiplier}x**\n\n"
                f"Тисни «ЗАБРАТИ ВИГРАШ», поки не впав!"
            )
            await update_live_messages(text_fly, kb_fly)
            await asyncio.sleep(0.8)

            game.current_multiplier = round(game.current_multiplier + step, 2)
            step += 0.03

            if game.current_multiplier >= game.target_multiplier:
                game.current_multiplier = game.target_multiplier
                break

        # --- ФАЗА 4: КРАШ ---
        game.crashed = True
        text_crash = (
            f"💥 **ЛІТАК КРАШНУВСЯ на {game.current_multiplier}x!**\n\n"
            f"📊 Раунд завершено.\n"
            f"Готуємо наступний запуск..."
        )
        await update_live_messages(text_crash, None)
        await asyncio.sleep(4)

# ==================== 4. МЕНЮ ТА КОМАНДИ ====================

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✈️ Грати (Crash)")],
            [KeyboardButton(text="👤 Профіль"), KeyboardButton(text="🎁 Бонус")],
            [KeyboardButton(text="🏆 Топ"), KeyboardButton(text="⭐ Купити Stars")]
        ],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    get_user(message.from_user.id, message.from_user.username or "Гравець")
    text = (
        "👋 **Вітаємо у Crash Game!**\n\n"
        "Незмінне правило: **зліт кожні 20 секунд!**\n"
        "Користуйтеся кнопками внизу екрана для навігації."
    )
    await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")
    await spawn_live_game(message.chat.id)

@dp.message(F.text == "✈️ Грати (Crash)")
@dp.message(Command("fly"))
async def handle_fly(message: types.Message):
    await spawn_live_game(message.chat.id)

async def spawn_live_game(chat_id: int):
    game.live_messages.pop(chat_id, None)

    if not game.is_running:
        kb_bet = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💵 1 ⭐", callback_data="bet_1"),
             InlineKeyboardButton(text="💵 5 ⭐", callback_data="bet_5"),
             InlineKeyboardButton(text="💵 10 ⭐", callback_data="bet_10")],
            [InlineKeyboardButton(text="✍️ Своя ставка", callback_data="custom_bet")]
        ])
        msg = await bot.send_message(
            chat_id, 
            "⏳ **ЛІТАК НА ЗАПРАВЦІ!**\nОчікуйте злету...", 
            reply_markup=kb_bet, 
            parse_mode="Markdown"
        )
    else:
        kb_fly = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 ЗАБРАТИ ВИГРАШ", callback_data="cashout")]
        ])
        msg = await bot.send_message(
            chat_id, 
            f"✈️ **ЛІТАК У ПОЛЬОТІ!**\n📈 Поточний X: **{game.current_multiplier}x**", 
            reply_markup=kb_fly, 
            parse_mode="Markdown"
        )
    
    game.live_messages[chat_id] = msg.message_id

@dp.message(F.text == "👤 Профіль")
@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    user = get_user(message.from_user.id, message.from_user.username or "Гравець")
    await message.answer(
        f"👤 **Профіль:** {user[1]}\n🆔 **ID:** `{user[0]}`\n💰 **Баланс:** `{user[2]}` ⭐", 
        parse_mode="Markdown"
    )

@dp.message(F.text == "🎁 Бонус")
@dp.message(Command("bonus"))
async def cmd_bonus(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.username or "Гравець")
    now = int(time.time())
    last_bonus = user[3]
    
    if now - last_bonus >= 86400:
        update_balance(user_id, 5)
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
        await message.answer(f"⏳ Бонус буде доступний через **{hours} год {minutes} хв**.")

@dp.message(F.text == "🏆 Топ")
@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
    leaders = cursor.fetchall()
    conn.close()

    text = "🏆 **ТОП-10 Гравців:**\n\n"
    for idx, (username, balance) in enumerate(leaders, 1):
        text += f"{idx}. **{username}** — `{balance}` ⭐\n"
    await message.answer(text, parse_mode="Markdown")

# ==================== 5. КНОПКИ ТА КАСТОМНА СТАВКА ====================

@dp.callback_query(F.data == "custom_bet")
async def ask_custom_bet(callback: types.CallbackQuery, state: FSMContext):
    if game.is_running:
        await callback.answer("❌ Літак уже летить! Зачекайте наступного раунду.", show_alert=True)
        return
    
    await state.set_state(GameStates.waiting_for_custom_bet)
    await callback.message.answer("✍️ **Введіть суму вашої ставки числом** (наприклад: 25):")
    await callback.answer()

@dp.message(GameStates.waiting_for_custom_bet)
async def process_custom_bet_input(message: types.Message, state: FSMContext):
    await state.clear()
    
    if game.is_running:
        await message.answer("❌ Раунд уже почався! Ваша ставка не прийнята.")
        return

    if not message.text.isdigit():
        await message.answer("❌ Будь ласка, введіть тільки ціле число!")
        return

    amount = int(message.text)
    if amount <= 0:
        await message.answer("❌ Ставка має бути більше 0!")
        return

    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.username or "Гравець")

    if user[2] < amount:
        await message.answer(f"❌ Недостатньо зірочок! Ваш баланс: {user[2]} ⭐")
        return

    update_balance(user_id, -amount)
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO bets (user_id, amount) VALUES (?, ?)", (user_id, amount))
    conn.commit()
    conn.close()

    await message.answer(f"✅ Ваша ставка **{amount} ⭐** успішно прийнята!")

@dp.callback_query(F.data.startswith("bet_"))
async def process_bet(callback: types.CallbackQuery):
    if game.is_running:
        await callback.answer("❌ Літак уже летить! Зачекайте наступного раунду.", show_alert=True)
        return

    amount = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    user = get_user(user_id, callback.from_user.username or "Гравець")

    if user[2] < amount:
        await callback.answer("❌ Нестача зірочок на балансі! Натисніть «🎁 Бонус»", show_alert=True)
        return

    update_balance(user_id, -amount)
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO bets (user_id, amount) VALUES (?, ?)", (user_id, amount))
    conn.commit()
    conn.close()

    await callback.answer(f"✅ Ставка {amount} ⭐ прийнята!", show_alert=True)

@dp.callback_query(F.data == "cashout")
async def process_cashout(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if not game.is_running or game.crashed:
        await callback.answer("💥 Літак уже впав!", show_alert=True)
        return

    if user_id not in game.bets or game.bets[user_id]["won"]:
        await callback.answer("❌ У вас немає активної ставки або ви вже забрали виграш!", show_alert=True)
        return

    bet_amount = game.bets[user_id]["amount"]
    win_amount = int(bet_amount * game.current_multiplier)
    
    game.bets[user_id]["won"] = True
    update_balance(user_id, win_amount)

    await callback.answer(f"🎉 Забрано {win_amount} ⭐ на {game.current_multiplier}x!", show_alert=True)

# ==================== 6. TELEGRAM STARS (ВІД 50 ДО 10 000) ====================

@dp.message(F.text == "⭐ Купити Stars")
@dp.message(Command("stars"))
async def cmd_stars(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ 50 Stars", callback_data="buy_50"),
         InlineKeyboardButton(text="⭐ 100 Stars", callback_data="buy_100")],
        [InlineKeyboardButton(text="⭐ 250 Stars", callback_data="buy_250"),
         InlineKeyboardButton(text="⭐ 500 Stars", callback_data="buy_500")],
        [InlineKeyboardButton(text="⭐ 1,000 Stars", callback_data="buy_1000"),
         InlineKeyboardButton(text="⭐ 2,500 Stars", callback_data="buy_2500")],
        [InlineKeyboardButton(text="⭐ 5,000 Stars", callback_data="buy_5000"),
         InlineKeyboardButton(text="⭐ 10,000 Stars", callback_data="buy_10000")]
    ])
    await message.answer("Оберіть пакет Telegram Stars ⭐ для поповнення балансу:", reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy_stars(callback: types.CallbackQuery):
    stars_count = int(callback.data.split("_")[1])
    prices = [LabeledPrice(label="Поповнення балансу", amount=stars_count)]
    
    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Поповнення Stars",
        description=f"Придбати {stars_count} Telegram Stars для гри в Crash",
        payload=f"stars_pack_{stars_count}",
        provider_token="",
        currency="XTR",
        prices=prices
    )
    await callback.answer()

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    stars_added = message.successful_payment.total_amount
    update_balance(message.from_user.id, stars_added)
    await message.answer(f"🎉 Дякуємо за підтримку! На ваш баланс зараховано **+{stars_added} ⭐**")

# ==================== 7. ЗАПУСК ====================

async def main():
    init_db()
    asyncio.create_task(crash_game_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
