"""
SQLite tabanlı basit veritabanı katmanı.
Prod'da Postgres'e geçilebilir, ama prototip için SQLite yeterli.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = "bot_click_guard.db"


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                campaign_id TEXT,
                ip_address TEXT NOT NULL,
                user_agent TEXT,
                gclid TEXT,
                landing_page TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS suspicious_ips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                reason TEXT,
                status TEXT DEFAULT 'PENDING',
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                synced_to_google_ads INTEGER DEFAULT 0,
                UNIQUE(account_id, ip_address)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                action TEXT NOT NULL,
                success INTEGER NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.utcnow().isoformat()
