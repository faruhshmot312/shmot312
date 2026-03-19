"""Парсинг данных из Google Sheets в текстовый формат для ИИ."""

from __future__ import annotations


def table_to_text(
    sheet_name: str,
    rows: list[list[str]],
    max_rows: int = 200,
) -> str:
    """Конвертирует лист таблицы в читаемый текст для Claude.

    Первая строка считается заголовком.
    Ограничивает вывод до max_rows строк (чтобы не превысить контекст).
    """
    if not rows:
        return f"Лист «{sheet_name}»: пуст"

    header = rows[0]
    data_rows = rows[1 : max_rows + 1]
    total = len(rows) - 1

    lines: list[str] = [f"## Лист «{sheet_name}» ({total} строк)"]
    lines.append("Столбцы: " + " | ".join(header))
    lines.append("---")

    for i, row in enumerate(data_rows, start=1):
        parts: list[str] = []
        for col_name, value in zip(header, row):
            if value.strip():
                parts.append(f"{col_name}: {value}")
        if parts:
            lines.append(f"{i}. " + " | ".join(parts))

    if total > max_rows:
        lines.append(f"... и ещё {total - max_rows} строк (показаны первые {max_rows})")

    return "\n".join(lines)


def spreadsheet_to_text(
    name: str,
    sheets_data: dict[str, list[list[str]]],
    max_rows_per_sheet: int = 200,
) -> str:
    """Конвертирует всю таблицу (все листы) в текст."""
    parts: list[str] = [f"# Таблица: {name}"]
    for sheet_name, rows in sheets_data.items():
        parts.append(table_to_text(sheet_name, rows, max_rows_per_sheet))
    return "\n\n".join(parts)
