import os
import asyncio
import logging
import random
import sqlite3
import time
import json
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
    ReplyKeyboardMarkup, KeyboardButton,
    LabeledPrice, PreCheckoutQuery
)
from aiogram.exceptions import TelegramBadRequest

BOT_TOKEN = os.getenv("BOT_TOKEN")

# 👑 Твій Telegram ID адміністратора
ADMIN_ID = 7842251789  

WEBAPP_URL = "https://mischenkobogdan802-boop.github.io/-telegram-game-bot/"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== СТАНИ FSM ====================
class GameStates(StatesGroup):
    waiting_for_custom_bet = State()
    waiting_for_broadcast = State()
    waiting_for_give_id = State()
    waiting_for_give_amount = State()

# ==================== 1. БАЗА ДАНИХ (SQLite) ====================
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            last_bonus INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            joined_date INTEGER DEFAULT 0,
            rakeback INTEGER DEFAULT 0,
            max_win INTEGER DEFAULT 0
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
    safe_username = username if username else "Гравець"
    now = int(time.time())
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance, last_bonus, wins, referrals, joined_date, rakeback, max_win FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("""
            INSERT INTO users (user_id, username, balance, last_bonus, wins, referrals, joined_date, rakeback, max_win) 
            VALUES (?, ?, 100, 0, 0, 0, ?, 0, 0)
        """, (user_id, safe_username, now))
        conn.commit()
        row = (user_id, safe_username, 100, 0, 0, 0, now, 0, 0)
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
        self.bets = {}
        self.live_messages = {}

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

# ==================== 3. АВТОМАТИЧНИЙ ЦИКЛ ====================
async def crash_game_loop():
    while True:
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

        game.crashed = True
        text_crash = (
            f"💥 **ЛІТАК КРАШНУВСЯ на {game.current_multiplier}x!**\n\n"
            f"📊 Раунд завершено.\n"
            f"Готуємо наступний запуск..."
        )
        await update_live_messages(text_crash, None)
        await asyncio.sleep(4)

# ==================== 4. МЕНЮ ТА КОМАНДИ ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_name = message.from_user.username or message.from_user.full_name or "Гравець"
    user_data = get_user(message.from_user.id, user_name)
    user_balance = user_data[2]

    user_webapp_url = f"{WEBAPP_URL}?balance={user_balance}"

    text = (
        "👋 **Вітаємо у Telegram Казино!**\n\n"
        "🎮 Натисніть кнопку **«📱 Відкрити Казино WebApp»** нижче, щоб запустити повноцінну ігрову платформу зі збереженим балансом!\n\n"
        "Або користуйтеся текстовим меню нижче."
    )
    
    inline_webapp_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Відкрити Казино WebApp 🚀", web_app=WebAppInfo(url=user_webapp_url))]
        ]
    )
    
    reply_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Відкрити WebApp (Казино)", web_app=WebAppInfo(url=user_webapp_url))],
            [KeyboardButton(text="✈️ Грати у Crash (Текст)")],
            [KeyboardButton(text="👤 Профіль"), KeyboardButton(text="🎁 Бонус")],
            [KeyboardButton(text="🏆 Топ"), KeyboardButton(text="⭐ Купити Stars")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(text, reply_markup=reply_kb, parse_mode="Markdown")
    await message.answer("👇 Запустити повноекранне казино:", reply_markup=inline_webapp_kb)
    await spawn_live_game(message.chat.id)

@dp.message(F.text == "✈️ Грати у Crash (Текст)")
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
    user_id = message.from_user.id
    display_name = message.from_user.username or message.from_user.full_name or "Гравець"
    user = get_user(user_id, display_name)
    
    current_balance = user[2]
    wins = user[4]
    referrals = user[5]
    joined_date = user[6]
    rakeback = user[7]
    max_win = user[8]
    
    days_with_us = max(1, (int(time.time()) - joined_date) // 86400)
    
    user_webapp_url = f"{WEBAPP_URL}?balance={current_balance}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Відкрити WebApp казино 🎮", web_app=WebAppInfo(url=user_webapp_url))]
    ])
    
    profile_text = (
        f"👤 **Профіль:** @{message.from_user.username or 'user'}\n"
        f"🏆 **Перемог:** {wins}\n"
        f"👥 **Рефералів:** {referrals}\n"
        f"⏳ **Днів з нами:** {days_with_us}\n"
        f"💎 **Найкращий виграш:** {max_win} ⭐\n\n"
        f"🎁 **Рейкбек:**\n"
        f"Повернення 6% від програшу в іграх\n"
        f"⭐ **{rakeback}** сума вашого рейкбеку\n\n"
        f"💰 **Баланс:** `{current_balance}` ⭐"
    )
    
    await message.answer(profile_text, reply_markup=kb, parse_mode="Markdown")

@dp.message(F.text == "🎁 Бонус")
@dp.message(Command("bonus"))
async def cmd_bonus(message: types.Message):
    user_id = message.from_user.id
    display_name = message.from_user.username or message.from_user.full_name or "Гравець"
    user = get_user(user_id, display_name)
    now = int(time.time())
    last_bonus = user[3]
    
    if now - last_bonus >= 86400:
        update_balance(user_id, 10)
        
        updated_user = get_user(user_id, display_name)
        new_balance = updated_user[2]
        
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now, user_id))
        conn.commit()
        conn.close()

        new_webapp_url = f"{WEBAPP_URL}?balance={new_balance}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Грати в казино 🎮", web_app=WebAppInfo(url=new_webapp_url))]
        ])

        await message.answer(
            f"🎁 Ви успішно отримали щоденний бонус: **+10 ⭐**!\n"
            f"💰 Ваш новий баланс: **{new_balance} ⭐**", 
            reply_markup=kb,
            parse_mode="Markdown"
        )
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
    cursor.execute("SELECT username, balance, wins FROM users ORDER BY balance DESC LIMIT 10")
    leaders = cursor.fetchall()
    conn.close()

    text = "🏆 **ТОП-10 Гравців казино:**\n\n"
    for idx, (username, balance, wins) in enumerate(leaders, 1):
        name = username if username else "Гравець"
        text += f"{idx}. **{name}** — `{balance}` ⭐ (Перемог: {wins})\n"
        
    await message.answer(text, parse_mode="Markdown")

# ==================== 5. АДМІН-ПАНЕЛЬ ====================

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(balance) FROM users")
    total_users, total_stars = cursor.fetchone()
    conn.close()

    text = (
        "👑 **АДМІН-ПАНЕЛЬ**\n\n"
        f"👥 Усього користувачів: `{total_users or 0}`\n"
        f"💎 Загальний баланс у казино: `{total_stars or 0}` ⭐\n\n"
        "Оберіть дію нижче:"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Розсилка новин", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="➕ / ➖ Видати/Забрати Stars", callback_data="admin_give")]
    ])

    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "admin_broadcast
