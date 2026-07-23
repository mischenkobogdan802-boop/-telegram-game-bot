import os
import sqlite3

DB_DIR = "/opt/render/project/src/data"
DB_PATH = os.path.join(DB_DIR, "bot.db")

os.makedirs(DB_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 1000,
    last_bonus INTEGER DEFAULT 0,
    games INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0
)
""")

conn.commit()


def get_user(user_id: int):
    cursor.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user_id,)
    )
    return cursor.fetchone()


def create_user(user_id: int, username: str):
    cursor.execute(
        """
        INSERT OR IGNORE INTO users(user_id, username)
        VALUES(?, ?)
        """,
        (user_id, username)
    )
    conn.commit()


def get_balance(user_id: int):
    cursor.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (user_id,)
    )
    row = cursor.fetchone()
    return row[0] if row else 0


def add_balance(user_id: int, amount: int):
    cursor.execute(
        """
        UPDATE users
        SET balance = balance + ?
        WHERE user_id=?
        """,
        (amount, user_id)
    )
    conn.commit()


def remove_balance(user_id: int, amount: int):
    cursor.execute(
        """
        UPDATE users
        SET balance = balance - ?
        WHERE user_id=?
        """,
        (amount, user_id)
    )
    conn.commit()
