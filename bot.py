import asyncio
import logging
import random
import sqlite3
import time
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton

# ==================== НАЛАШТУВАННЯ ====================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Вставте ваш токен від BotFather

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== БАЗА ДАНИХ (SQLite) ====================
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 100,
            last_bonus INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            user_id INTEGER PRIMARY KEY,
            amount INTEGER,
            auto_withdraw REAL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id: int, username: str = "User"):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance, last_bonus FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)", (user_id, username, 100))
        conn.commit()
        row = (user_id, username, 100, 0)
    conn.close()
    return row

def update_balance(user_id: int, delta: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (delta, user_id))
    conn.commit()
    conn.close()

# ==================== СТАН ГРИ (CRASH) ====================
class CrashGame:
    def __init__(self):
        self.is_running = False
        self.current_multiplier = 1.00
        self.crashed = False
        self.bets = {}  # user_id: {"amount": int, "username": str, "won": bool}

    def generate_crash_multiplier(self) -> float:
        # Шанси:
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

# ==================== ТАЙМЕР І ЦИКЛ ГРИ ====================
async def crash_game_loop():
    while True:
        # 1. Фаза очікування ставок (15 секунд)
        game.is_running = False
        game.crashed = False
        game.bets.clear()

        # Зчитуємо всі ставки з БД
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bets")
        conn.commit()
        conn.close()

        await asyncio.sleep(15)

        # 2. Початок польоту
        game.is_running = True
        target_multiplier = game.generate_crash_multiplier()
        game.current_multiplier = 1.00

        # Збираємо всі ставки з БД
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT b.user_id, b.amount, u.username FROM bets b JOIN users u ON b.user_id = u.user_id")
        current_bets = cursor.fetchall()
        conn.close()

        for u_id, amt, u_name in current_bets:
            game.bets[u_id] = {"amount": amt, "username": u_name, "won": False}

        # Імітація польоту
        while game.current_multiplier < target_multiplier:
            await asyncio.sleep(1)
            game.current_multiplier = round(game.current_multiplier + random.uniform(0.1, 0.3), 2)
            if game.current_multiplier >= target_multiplier:
                game.current_multiplier = target_multiplier
                break

        # Краш
        game.crashed = True
        await asyncio.sleep(5)  # Пауза перед наступним раундом

# ==================== ОБРОБНИКИ КОМАНД ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    get_user(message.from_user.id, message.from_user.username or "Користувач")
    text = (
        "✈️ **Ласкаво просимо до Crash Game!**\n\n"
        "Кожні 20 секунд злітає новий літак!\n"
        "Встигни забрати виграш до того, як він улетить!\n\n"
        "📌 **Команди:**\n"
        "🔹 /fly — Подивитися поточний політ та зробити ставку\n"
        "🔹 /profile — Особистий профіль та баланс\n"
        "🔹 /bonus — Отримати щоденний бонус\n"
        "🔹 /top — Рейтинг гравців\n"
        "🔹 /stars — Поповнити баланс через Telegram Stars ⭐"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    user = get_user(message.from_user.id, message.from_user.username or "Користувач")
    text = (
        f"👤 **Профіль:** {user[1]}\n"
        f"🆔 **ID:** `{user[0]}`\n"
        f"💰 **Баланс:** `{user[2]}` Stars ⭐"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("bonus"))
async def cmd_bonus(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id, message.from_user.username or "Користувач")
    now = int(time.time())
    last_bonus = user[3]

    if now - last_bonus >= 86400:  # 24 години
        bonus_amount = 25
        update_balance(user_id, bonus_amount)
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now, user_id))
        conn.commit()
        conn.close()
        await message.answer(f"🎁 Ви отримали щоденний бонус: **+{bonus_amount} Stars**!")
    else:
        remaining = 86400 - (now - last_bonus)
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await message.answer(f"⏳ Бонус буде доступний через **{hours} год. {minutes} хв.**")

@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
    leaders = cursor.fetchall()
    conn.close()

    text = "🏆 **ТОП-10 Гравців:**\n\n"
    for idx, (username, balance) in enumerate(leaders, 1):
        text += f"{idx}. **{username}** — {balance} ⭐\n"
    await message.answer(text, parse_mode="Markdown")

# ==================== МЕХАНІКА ГРИ (CRASH) ====================

@dp.message(Command("fly"))
async def cmd_fly(message: types.Message):
    if not game.is_running:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💵 Зробити ставку (10 Stars)", callback_data="bet_10")],
            [InlineKeyboardButton(text="💵 Зробити ставку (50 Stars)", callback_data="bet_50")]
        ])
        await message.answer("⏳ **Літак готується до злету!**\nЗробіть вашу ставку до стартy:", reply_markup=kb)
    else:
        if game.crashed:
            await message.answer(f"💥 **LIKAT КРАШНУВСЯ на {game.current_multiplier}x!**\nЧекаємо наступного раунду...")
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 ЗАБРАТИ ВІИГРАШ", callback_data="cashout")]
            ])
            await message.answer(f"✈️ **Літак у польоті!**\nПоточний коефіцієнт: **{game.current_multiplier}x**", reply_markup=kb)

@dp.callback_query(F.data.startswith("bet_"))
async def process_bet(callback: types.CallbackQuery):
    if game.is_running:
        await callback.answer("❌ Гра вже почалася! Зачекайте наступного раунду.", show_alert=True)
        return

    amount = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    user = get_user(user_id, callback.from_user.username or "Користувач")

    if user[2] < amount:
        await callback.answer("❌ Нестача балансу!", show_alert=True)
        return

    # Записуємо ставку
    update_balance(user_id, -amount)
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO bets (user_id, amount) VALUES (?, ?)", (user_id, amount))
    conn.commit()
    conn.close()

    await callback.answer(f"✅ Ставка {amount} Stars прийнята!")
    await callback.message.edit_text(f"🎯 Ваша ставка: **{amount} Stars**.\nОчікуйте вильоту...")

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

    await callback.answer(f"🎉 Ви забрали {win_amount} Stars (x{game.current_multiplier})!", show_alert=True)
    await callback.message.edit_text(f"✅ Ви успішно забрали **{win_amount} Stars** на коефіцієнті **{game.current_multiplier}x**!")

# ==================== ОПЛАТА TELEGRAM STARS ====================

@dp.message(Command("stars"))
async def cmd_stars(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Купити 50 Stars", callback_data="buy_50")],
        [InlineKeyboardButton(text="⭐ Купити 100 Stars", callback_data="buy_100")]
    ])
    await message.answer("Оберіть кількість Telegram Stars для поповнення балансу:", reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy_stars(callback: types.CallbackQuery):
    stars_count = int(callback.data.split("_")[1])
    
    prices = [LabeledPrice(label="Поповнення балансу", amount=stars_count)]
    
    await callback.bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Поповнення Stars",
        description=f"Придбати {stars_count} Telegram Stars для гри в Crash",
        payload=f"stars_pack_{stars_count}",
        provider_token="",  # Для Telegram Stars залишається порожнім!
        currency="XTR",     # Валюта Telegram Stars
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
    await message.answer(f"🎉 Дякуємо за підтримку! На ваш баланс зараховано **{stars_added} Stars** ⭐")

# ==================== ЗАПУСК БОТА ====================

async def main():
    init_db()
    # Запускаємо фоновий цикл гри
    asyncio.create_task(crash_game_loop())
    # Запускаємо поллінг бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
