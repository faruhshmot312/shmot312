"""SQLite база для кэширования данных из Google Sheets и Bitrix24."""

from __future__ import annotations

import aiosqlite

from config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS sheets_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spreadsheet_url TEXT NOT NULL,
    sheet_name TEXT NOT NULL,
    data_json TEXT NOT NULL,
    row_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(spreadsheet_url, sheet_name)
);

CREATE TABLE IF NOT EXISTS sheets_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spreadsheet_name TEXT NOT NULL,
    sheet_name TEXT NOT NULL,
    columns TEXT NOT NULL,
    row_count INTEGER DEFAULT 0,
    sample_data TEXT DEFAULT '',
    description TEXT DEFAULT '',
    UNIQUE(spreadsheet_name, sheet_name)
);

CREATE TABLE IF NOT EXISTS bitrix_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_type TEXT NOT NULL UNIQUE,
    data_json TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_key TEXT NOT NULL,
    message TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


async def get_db() -> aiosqlite.Connection:
    """Открывает соединение с БД и создаёт таблицы если нужно."""
    db = await aiosqlite.connect(config.DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA)
    await db.commit()
    return db
