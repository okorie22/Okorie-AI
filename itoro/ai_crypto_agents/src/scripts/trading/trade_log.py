import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'live_trades.db')

def _ensure_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS live_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                signature TEXT,
                side TEXT NOT NULL,
                size REAL NOT NULL,
                price_usd REAL,
                usd_value REAL,
                agent TEXT,
                token TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

def log_live_trade(signature: str, side: str, size: float, price_usd: float, usd_value: float, agent: str, token: str):
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO live_trades (timestamp, signature, side, size, price_usd, usd_value, agent, token) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().strftime('%H:%M:%S'), signature or '', side, float(size or 0), float(price_usd or 0), float(usd_value or 0), agent or '', token or '')
        )
        conn.commit()
    finally:
        conn.close()

def get_recent_live_trades(limit: int = 5):
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute("SELECT timestamp, signature, side, size, price_usd, usd_value, agent, token FROM live_trades ORDER BY id DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        return [
            {
                'timestamp': r[0],
                'signature': r[1],
                'side': r[2],
                'size': r[3],
                'price_usd': r[4],
                'usd_value': r[5],
                'agent': r[6],
                'token': r[7]
            }
            for r in rows
        ]
    finally:
        conn.close()


