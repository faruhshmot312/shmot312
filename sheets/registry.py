"""Реестр подключённых Google Sheets таблиц.

Хранит список таблиц в JSON файле рядом с ботом.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

REGISTRY_PATH = Path(__file__).parent.parent / "sheets_registry.json"


@dataclass
class SheetEntry:
    name: str  # Человекочитаемое название ("ДДС", "Закупки")
    url: str  # Полная ссылка на Google Sheets
    description: str = ""  # Описание содержимого


def load_registry() -> list[SheetEntry]:
    """Загружает реестр таблиц из файла."""
    if not REGISTRY_PATH.exists():
        return []
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return [SheetEntry(**entry) for entry in data]


def save_registry(entries: list[SheetEntry]) -> None:
    """Сохраняет реестр таблиц в файл."""
    data = [asdict(entry) for entry in entries]
    REGISTRY_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_sheet(name: str, url: str, description: str = "") -> SheetEntry:
    """Добавляет таблицу в реестр."""
    entries = load_registry()
    # Не добавляем дубликаты по URL
    for entry in entries:
        if entry.url == url:
            entry.name = name
            entry.description = description
            save_registry(entries)
            return entry
    new_entry = SheetEntry(name=name, url=url, description=description)
    entries.append(new_entry)
    save_registry(entries)
    return new_entry


def remove_sheet(url: str) -> bool:
    """Удаляет таблицу из реестра по URL."""
    entries = load_registry()
    filtered = [e for e in entries if e.url != url]
    if len(filtered) == len(entries):
        return False
    save_registry(filtered)
    return True
