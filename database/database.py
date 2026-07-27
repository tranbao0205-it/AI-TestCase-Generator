"""
Database module - SQLite initialization and connection management.
Stores conversation history and file records.
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'app.db')


def init_db():
    """Initialize the SQLite database with required tables."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            excel_file  TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id    INTEGER NOT NULL,
            role               TEXT    NOT NULL,
            content            TEXT    NOT NULL,
            context_mode       TEXT    DEFAULT 'new',
            parent_snapshot_id INTEGER,
            excel_file         TEXT,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_snapshot_id) REFERENCES messages(id) ON DELETE SET NULL
        )
    ''')

    message_columns = {row[1] for row in cursor.execute("PRAGMA table_info(messages)").fetchall()}
    if 'context_mode' not in message_columns:
        cursor.execute("ALTER TABLE messages ADD COLUMN context_mode TEXT DEFAULT 'new'")
    if 'parent_snapshot_id' not in message_columns:
        cursor.execute("ALTER TABLE messages ADD COLUMN parent_snapshot_id INTEGER")
    if 'excel_file' not in message_columns:
        cursor.execute("ALTER TABLE messages ADD COLUMN excel_file TEXT")

    cursor.execute(
        'CREATE INDEX IF NOT EXISTS idx_messages_conversation_role '
        'ON messages(conversation_id, role, id)'
    )
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_records (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            filename        TEXT    NOT NULL UNIQUE,
            project_name    TEXT,
            test_case_count INTEGER DEFAULT 0,
            conversation_id INTEGER,
            snapshot_id     INTEGER,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    file_columns = {row[1] for row in cursor.execute("PRAGMA table_info(file_records)").fetchall()}
    if 'conversation_id' not in file_columns:
        cursor.execute("ALTER TABLE file_records ADD COLUMN conversation_id INTEGER")
    if 'snapshot_id' not in file_columns:
        cursor.execute("ALTER TABLE file_records ADD COLUMN snapshot_id INTEGER")
    cursor.execute(
        'CREATE INDEX IF NOT EXISTS idx_file_records_snapshot '
        'ON file_records(snapshot_id, created_at)'
    )
    conn.commit()
    conn.close()


def get_db() -> sqlite3.Connection:
    """Open and return a database connection with Row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
