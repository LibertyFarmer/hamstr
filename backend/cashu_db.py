"""
Cashu wallet database - kept fully separate from notes.db so that
note-management operations (clearing, resetting) can never touch wallet data.
"""
import os
import sqlite3
from socketio_logger import get_socketio_logger

socketio_logger = get_socketio_logger()


def get_cashu_db_path(base_dir):
    return os.path.join(base_dir, 'data', 'cashu.db')


def init_cashu_db(base_dir):
    db_path = get_cashu_db_path(base_dir)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS proofs
                     (id TEXT PRIMARY KEY,
                      amount INTEGER,
                      secret TEXT,
                      C TEXT,
                      keyset_id TEXT,
                      mint_url TEXT,
                      state TEXT DEFAULT 'unspent',
                      created_at INTEGER)''')

        c.execute('''CREATE TABLE IF NOT EXISTS mints
                     (url TEXT PRIMARY KEY,
                      name TEXT,
                      active INTEGER DEFAULT 1,
                      keyset_id TEXT)''')

        c.execute('''CREATE TABLE IF NOT EXISTS cashu_transactions
                     (id TEXT PRIMARY KEY,
                      type TEXT,
                      amount INTEGER,
                      memo TEXT,
                      event_id TEXT,
                      timestamp INTEGER)''')

        conn.commit()
        socketio_logger.info("[CASHU_DB] Database initialization completed successfully")
    except Exception as e:
        socketio_logger.error(f"[CASHU_DB] Error initializing database: {e}")
    finally:
        conn.close()