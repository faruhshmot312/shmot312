"""Google Sheets API клиент — подключение и чтение данных."""

from __future__ import annotations

import asyncio
import logging

import gspread
from google.oauth2.service_account import Credentials

from config import config

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

_client: gspread.Client | None = None
_creds: Credentials | None = None


def get_client() -> gspread.Client:
    """Возвращает авторизованный gspread клиент с автообновлением токена."""
    global _client, _creds
    if _creds is None:
        _creds = Credentials.from_service_account_file(
            config.GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
        )
    if _creds.expired or not _creds.valid:
        from google.auth.transport.requests import Request
        _creds.refresh(Request())
        _client = None  # пересоздаём клиент с новым токеном
    if _client is None:
        _client = gspread.authorize(_creds)
    return _client


def read_spreadsheet(spreadsheet_url: str) -> dict[str, list[list[str]]]:
    """Читает все листы таблицы и возвращает {sheet_name: [[row], ...]}."""
    client = get_client()
    spreadsheet = client.open_by_url(spreadsheet_url)
    result: dict[str, list[list[str]]] = {}
    for worksheet in spreadsheet.worksheets():
        result[worksheet.title] = worksheet.get_all_values()
    return result


async def read_spreadsheet_async(spreadsheet_url: str) -> dict[str, list[list[str]]]:
    """Асинхронная обёртка — не блокирует event loop."""
    return await asyncio.to_thread(read_spreadsheet, spreadsheet_url)


def read_worksheet(spreadsheet_url: str, sheet_name: str) -> list[list[str]]:
    """Читает конкретный лист таблицы."""
    client = get_client()
    spreadsheet = client.open_by_url(spreadsheet_url)
    worksheet = spreadsheet.worksheet(sheet_name)
    return worksheet.get_all_values()


async def read_worksheet_async(spreadsheet_url: str, sheet_name: str) -> list[list[str]]:
    """Асинхронная обёртка для чтения конкретного листа."""
    return await asyncio.to_thread(read_worksheet, spreadsheet_url, sheet_name)
