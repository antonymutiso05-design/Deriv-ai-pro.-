"""SQLite storage for paper trades."""
import sqlite3
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    bet TEXT NOT NULL,
    digit INTEGER NOT NULL,
    win INTEGER NOT NULL,
    p REAL NOT NULL,
    pnl REAL NOT NULL
)
"""


def _conn(path):
    conn = sqlite3.connect(path, timeout=10)
    conn.execute(SCHEMA)
    return conn


def add_trade(path, ts, symbol, bet, digit, win, p, pnl):
    with _conn(path) as conn:
        conn.execute(
            "INSERT INTO trades (ts, symbol, bet, digit, win, p, pnl) VALUES (?,?,?,?,?,?,?)",
            (ts, symbol, bet, int(digit), int(win), float(p), float(pnl)),
        )


def load_trades(path):
    with _conn(path) as conn:
        return pd.read_sql_query("SELECT * FROM trades ORDER BY id", conn)


def clear_trades(path):
    with _conn(path) as conn:
        conn.execute("DELETE FROM trades")
