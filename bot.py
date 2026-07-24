import os
import asyncio
import logging
import random
import sqlite3
import time
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from aiogram.exceptions import TelegramBadRequest

# Отримуємо токен з налаштувань Render
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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

    def generate_crash_multiplier(self) -> float:
        # Шанси за вимогою:
        # 1.00 - 1.50X : 70%
        # 1.50 - 4.00X : 25%
        # 4.00 - 50.00X : 5%
        rand = random.random()
        if rand < 0.70:
            return round(random.uniform(1.00, 1.50), 2)
        elif rand < 0.95:
            return round(random.uniform(1.50, 4.00), 2)
        else:
            return round(random.uniform(4.00, 50.00), 2)

game = CrashGame()

# ==================== 3. АВТОМАТИЧНИЙ ЦИКЛ ПОЛЬОТУ (20 сек) ====================
async def crash_game_loop():
    while True:
        # --- ФАЗА 1: Очікування ставок (12 секунд) ---
        game.is_running = False
        game.crashed = False
        game.bets.clear()

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bets")
        conn.commit()
        conn.close()

        await asyncio.sleep(12)

        # --- ФАЗА 2: Початок польоту ---
        game.is_running = True
        game.target_multiplier = game.generate_crash_multiplier()
        game.current_multiplier = 1.00

        # Збираємо всі ставки з БД
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT b.user_id, b.amount, u.username FROM bets b JOIN users u ON b.user_id = u.user_id")
        current_bets = cursor.fetchall()
        conn.close()

        for u_id, amt, u_name in current_bets:
            game.bets[u_id] = {"amount": amt, "username": u_name, "won": False}

        # --- ФАЗА 3: Анімація польоту ---
        step = 0.05
        while game.current_multiplier < game.target_multiplier:
            await asyncio.sleep(0.8)
            game.current_multiplier = round(game.current_multiplier + step, 2)
            step += 0.02
            
            if game.current_multiplier >= game.target_multiplier:
                game.current_multiplier = game.target_multiplier
                break

        # --- ФАЗА 4: КРАШ ---
        game.crashed = True
        await asyncio.sleep(4)

# ==================== 4. КОМАНДИ БОТА ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    get_user(message.from_user.id, message.from_user.username or "Гравець")
    text = (
        "👋 **Ласкаво просимо до Crash Game!**\n\n"
        "✈️ Літак злітає кожні 20 секунд!\n"
        "Забирай виграш до того, як він улетить!\n\n"
        "📌 **Команди:**\n"
        "🔹 /fly — Вікно гри та ставка\n"
        "🔹 /profile — Особистий профіль та баланс\n"
        "🔹 /bonus — Щоденний бонус (+5 ⭐)\n"
        "🔹 /top — Таблиця лідерів\n"
        "🔹 /stars — Купити Telegram Stars ⭐"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    user = get_user(message.from_user.id, message.from_user.username or "Гравець")
    text = (
        f"👤 **Профіль:** {user[1]}\n"
        f"🆔 **ID:** `{user[0]}`\n"
        f"💰 **Баланс:** `{user[2]}` ⭐"
    )
    await message.answer(text, parse_mode="Markdown")

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

@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
    leaders = cursor.fetchall()
    conn.close()

    text = "🏆 **ТОП-10 Гравців за балансом:**\n\n"
    for idx, (username, balance) in enumerate(leaders, 1):
        text += f"{idx}. **{username}** — `{balance}` ⭐\n"
    await message.answer(text, parse_mode="Markdown")

# ==================== 5. МЕХАНІКА ГРИ (/fly) ====================

@dp.message(Command("fly"))
async def cmd_fly(message: types.Message):
    if not game.is_running:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💵 Ставка 1 ⭐", callback_data="bet_1"),
             InlineKeyboardButton(text="💵 Ставка 5 ⭐", callback_data="bet_5")],
            [InlineKeyboardButton(text="🔄 Оновити статус", callback_data="refresh_game")]
        ])
        await message.answer("⏳ **Літак готується до злету!**\nЗробіть вашу ставку до стартy:", reply_markup=kb)
    else:
        if game.crashed:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Наступний раунд", callback_data="refresh_game")]
            ])
            await message.answer(f"💥 **ЛІТАК КРАШНУВСЯ на {game.current_multiplier}x!**", reply_markup=kb)
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 ЗАБРАТИ ВИГРАШ", callback_data="cashout")],
                [InlineKeyboardButton(text="🔄 Оновити x", callback_data="refresh_game")]
            ])
            await message.answer(f"✈️ **Літак у польоті!**\nПоточний x: **{game.current_multiplier}x**", reply_markup=kb)

@dp.callback_query(F.data == "refresh_game")
async def process_refresh(callback: types.CallbackQuery):
    try:
        if not game.is_running:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💵 Ставка 1 ⭐", callback_data="bet_1"),
                 InlineKeyboardButton(text="💵 Ставка 5 ⭐", callback_data="bet_5")],
                [InlineKeyboardButton(text="🔄 Оновити статус", callback_data="refresh_game")]
            ])
            await callback.message.edit_text("⏳ **Літак готується до злету!**\nЗробіть вашу ставку до стартy:", reply_markup=kb)
        elif game.crashed:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Наступний раунд", callback_data="refresh_game")]
            ])
            await callback.message.edit_text(f"💥 **ЛІТАК КРАШНУВСЯ на {game.current_multiplier}x!**\nЧекаємо наступного раунду...", reply_markup=kb)
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 ЗАБРАТИ ВИГРАШ", callback_data="cashout")],
                [InlineKeyboardButton(text="🔄 Оновити x", callback_data="refresh_game")]
            ])
            await callback.message.edit_text(f"✈️ **Літак у польоті!**\nПоточний x: **{game.current_multiplier}x**", reply_markup=kb)
    except TelegramBadRequest:
        pass
    await callback.answer()

@dp.callback_query(F.data.startswith("bet_"))
async def process_bet(callback: types.CallbackQuery):
    if game.is_running:
        await callback.answer("❌ Гра вже почалася! Зачекайте наступного раунду.", show_alert=True)
        return

    amount = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    user = get_user(user_id, callback.from_user.username or "Гравець")

    if user[2] < amount:
        await callback.answer("❌ Недостатньо зірочок на балансі! Скористайтесь /bonus або /stars", show_alert=True)
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
    await callback.message.edit_text(f"✅ **Виграш!** Ви забрали **{win_amount} ⭐** (x{game.current_multiplier})!")

# ==================== 6. ПОПОВНЕННЯ TELEGRAM STARS ====================

@dp.message(Command("stars"))
async def cmd_stars(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Придбати 10 Stars", callback_data="buy_10")],
        [InlineKeyboardButton(text="⭐ Придбати 50 Stars", callback_data="buy_50")]
    ])
    await message.answer("Оберіть пакет Telegram Stars для поповнення балансу:", reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy_stars(callback: types.CallbackQuery):
    stars_count = int(callback.data.split("_")[1])
    
    prices = [LabeledPrice(label="Поповнення балансу", amount=stars_count)]
    
    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Поповнення балансу",
        description=f"Придбати {stars_count} Telegram Stars для гри в Crash",
        payload=f"stars_pack_{stars_count}",
        provider_token="",  # ДЛЯ TELEGRAM STARS ЗАЛИШАЄТЬСЯ ПОРОЖНІМ!
        currency="XTR",     # ВАЛЮТА TELEGRAM STARS
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
    await message.answer(f"🎉 Дякуємо за поповнення! На ваш баланс зараховано **+{stars_added} ⭐**")

# ==================== 7. ЗАПУСК БОТА ====================

async def main():
    init_db()
    asyncio.create_task(crash_game_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
