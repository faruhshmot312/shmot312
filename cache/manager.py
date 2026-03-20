"""CacheManager — загрузка, обновление и чтение данных из кэша."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta

from cache.db import get_db
from config import config
from sheets.client import read_spreadsheet_async
from sheets.registry import load_registry

logger = logging.getLogger(__name__)


async def refresh_sheets_cache() -> None:
    """Обновляет кэш всех Google Sheets таблиц."""
    entries = load_registry()
    if not entries:
        return

    db = await get_db()
    for entry in entries:
        try:
            sheets_data = await read_spreadsheet_async(entry.url)
            for sheet_name, rows in sheets_data.items():
                data_json = json.dumps(rows, ensure_ascii=False)
                row_count = len(rows)

                await db.execute(
                    """INSERT INTO sheets_cache (spreadsheet_url, sheet_name, data_json, row_count, updated_at)
                       VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(spreadsheet_url, sheet_name)
                       DO UPDATE SET data_json=excluded.data_json,
                                     row_count=excluded.row_count,
                                     updated_at=CURRENT_TIMESTAMP""",
                    (entry.url, sheet_name, data_json, row_count),
                )

                # Метаданные для маршрутизатора
                columns = json.dumps(rows[0] if rows else [], ensure_ascii=False)
                sample = json.dumps(rows[:4] if rows else [], ensure_ascii=False)
                await db.execute(
                    """INSERT INTO sheets_meta (spreadsheet_name, sheet_name, columns, row_count, sample_data, description)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(spreadsheet_name, sheet_name)
                       DO UPDATE SET columns=excluded.columns,
                                     row_count=excluded.row_count,
                                     sample_data=excluded.sample_data""",
                    (entry.name, sheet_name, columns, row_count, sample, entry.description),
                )

            logger.info("Кэш обновлён: %s (%d листов)", entry.name, len(sheets_data))
        except Exception as e:
            logger.error("Ошибка обновления кэша %s: %s %s", entry.name, type(e).__name__, e)

    await db.commit()


async def refresh_bitrix_cache() -> None:
    """Обновляет кэш данных Bitrix24."""
    if not config.BITRIX24_WEBHOOK_URL:
        return

    from bitrix.client import BitrixClient

    db = await get_db()
    client = BitrixClient()
    try:
        # Сделки за последние 90 дней
        deals = await client.get_recent_deals(days=90)
        await _save_bitrix(db, "deals", deals)

        # Статистика воронки
        pipeline = await client.get_pipeline_stats()
        await _save_bitrix(db, "pipeline_stats", pipeline)

        # Пользователи (менеджеры)
        users = await client.get_users()
        await _save_bitrix(db, "users", users)

        await db.commit()
        logger.info("Кэш Bitrix24 обновлён: %d сделок", len(deals))
    except Exception as e:
        logger.error("Ошибка обновления Bitrix24 кэша: %s", e)


async def _save_bitrix(db, data_type: str, data) -> None:
    data_json = json.dumps(data, ensure_ascii=False, default=str)
    await db.execute(
        """INSERT INTO bitrix_cache (data_type, data_json, updated_at)
           VALUES (?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(data_type)
           DO UPDATE SET data_json=excluded.data_json, updated_at=CURRENT_TIMESTAMP""",
        (data_type, data_json),
    )


async def refresh_all() -> None:
    """Обновляет весь кэш (Sheets + Bitrix24)."""
    await asyncio.gather(
        refresh_sheets_cache(),
        refresh_bitrix_cache(),
    )


async def is_cache_fresh() -> bool:
    """Проверяет, свежий ли кэш."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT MIN(updated_at) as oldest FROM sheets_cache"
    )
    row = await cursor.fetchone()
    if not row or not row["oldest"]:
        return False
    oldest = datetime.fromisoformat(row["oldest"])
    return datetime.utcnow() - oldest < timedelta(minutes=config.CACHE_TTL_MINUTES)


async def get_sheets_meta() -> list[dict]:
    """Возвращает метаданные всех листов для маршрутизатора."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT spreadsheet_name, sheet_name, columns, row_count, sample_data, description FROM sheets_meta"
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_sheet_data(spreadsheet_name: str, sheet_name: str) -> list[list[str]]:
    """Возвращает данные конкретного листа из кэша."""
    db = await get_db()
    entries = load_registry()
    url = None
    for entry in entries:
        if entry.name == spreadsheet_name:
            url = entry.url
            break

    if not url:
        return []

    cursor = await db.execute(
        "SELECT data_json FROM sheets_cache WHERE spreadsheet_url=? AND sheet_name=?",
        (url, sheet_name),
    )
    row = await cursor.fetchone()
    if row:
        return json.loads(row["data_json"])
    return []


async def get_all_sheets_data() -> dict[str, dict[str, list[list[str]]]]:
    """Возвращает все данные из кэша: {spreadsheet_name: {sheet_name: rows}}."""
    db = await get_db()
    entries = load_registry()
    url_to_name = {e.url: e.name for e in entries}

    cursor = await db.execute("SELECT spreadsheet_url, sheet_name, data_json FROM sheets_cache")
    rows = await cursor.fetchall()

    result: dict[str, dict[str, list[list[str]]]] = {}
    for row in rows:
        name = url_to_name.get(row["spreadsheet_url"], row["spreadsheet_url"])
        if name not in result:
            result[name] = {}
        result[name][row["sheet_name"]] = json.loads(row["data_json"])
    return result


async def get_bitrix_data(data_type: str) -> dict | list | None:
    """Возвращает данные Bitrix24 из кэша."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT data_json FROM bitrix_cache WHERE data_type=?", (data_type,)
    )
    row = await cursor.fetchone()
    if row:
        return json.loads(row["data_json"])
    return None
