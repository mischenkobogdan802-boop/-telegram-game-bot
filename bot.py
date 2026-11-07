import sqlite3
import time
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice

TOKEN = "ТВІЙ_ТОКЕН_БОТА"  # Заміни на свій токен від BotFather
WEBAPP_URL = "https://ТВІЙ_ЛОГІН.github.io/ТВІЙ_РЕПОЗИТОРІЙ/" # Посилання на GitHub Pages

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
    args = message.text.split()
    user_id = message.from_user.id
    username = message.from_user.username or "Гравець"
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute("INSERT INTO users (user_id, username, balance, wins, referrals, referred_by, joined_date) VALUES (?, ?, 0, 0, 0, 0, ?)", 
                       (user_id, username, int(time.time())))
        conn.commit()
    conn.close()

    # Якщо користувач натиснув поповнення у вебзастосунку і бот перенаправив його сюди
    if len(args) > 1 and args[1].startswith("pay_"):
        try:
            amount = int(args[1].replace("pay_", ""))
            if 10 <= amount <= 99999:
                prices = [LabeledPrice(label=f"Поповнення {amount} Stars", amount=amount)]
                await bot.send_invoice(
                    chat_id=user_id,
                    title="Поповнення балансу",
                    description=f"Придбати {amount} ⭐ для гри в казино",
                    payload=f"topup_{amount}",
                    currency="XTR",  # Офіційна валюта Telegram Stars
                    prices=prices
                )
                return
        except ValueError:
            pass

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Відкрити Казино WebApp", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])

    await message.answer(
        "👋 Вітаємо у Telegram Казино!\n\n"
        "Натисніть кнопку нижче, щоб відкрити ігрову платформу:",
        reply_markup=keyboard
    )

@dp.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# Зірки зараховуються ВИКЛЮЧНО після успішної оплати через Telegram
@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload
    
    if payload.startswith("topup_"):
        amount = int(payload.split("_")[1])
        user_id = message.from_user.id
        
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        new_balance = cursor.fetchone()[0]
        conn.close()
        
        await message.answer(
            f"✅ Успішно! З вашого рахунку списано зірки, і баланс поповнено на **{amount} ⭐**.\n"
            f"💰 Поточний баланс: **{new_balance} ⭐**\n\n"
            f"Тепер ви можете повернутися у застосунок — баланс оновиться автоматично!",
            parse_mode="Markdown"
        )

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

if __name__ == "__main__":
    print("Бот запущено...")
    dp.run_polling(bot)
