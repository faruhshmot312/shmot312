"""Claude API интеграция — двухэтапный ИИ: маршрутизатор + аналитик."""

from __future__ import annotations

import asyncio
import json
import logging

import anthropic

from ai.prompts import SYSTEM_PROMPT, ROUTER_PROMPT, DAILY_REPORT_PROMPT, WEEKLY_REPORT_PROMPT, ANALYTICS_PROMPT
from cache.manager import get_sheets_meta, get_sheet_data, get_bitrix_data, get_all_sheets_data
from config import config
from sheets.parser import spreadsheet_to_text, table_to_text

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


async def route_question(question: str) -> dict:
    """Шаг 1: определяет какие данные нужны для ответа на вопрос."""
    meta = await get_sheets_meta()
    if not meta:
        return {"sheets": [], "need_bitrix": True, "bitrix_data": ["deals", "pipeline_stats"]}

    # Формируем описание доступных данных
    sources_desc = "## Доступные Google Sheets:\n"
    for m in meta:
        cols = json.loads(m["columns"]) if m["columns"] else []
        cols_str = ", ".join(cols[:10])
        sources_desc += f"- {m['spreadsheet_name']} / {m['sheet_name']} ({m['row_count']} строк) — столбцы: {cols_str}\n"

    sources_desc += "\n## Bitrix24 CRM:\n"
    sources_desc += "- deals: сделки за 90 дней (суммы, стадии, менеджеры, даты, оплаты)\n"
    sources_desc += "- pipeline_stats: воронка продаж (конверсии по стадиям)\n"
    sources_desc += "- users: сотрудники/менеджеры\n"
    sources_desc += "- debitors: должники (остаток оплаты > 0)\n"
    sources_desc += "- overdue: просроченные заказы\n"

    client = get_client()
    for attempt in range(3):
        try:
            response = await client.messages.create(
                model=config.AI_ROUTER_MODEL,
                max_tokens=1024,
                system=ROUTER_PROMPT,
                messages=[{"role": "user", "content": f"{sources_desc}\n\nВопрос: {question}"}],
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
            return json.loads(text)
        except anthropic.RateLimitError:
            wait = (attempt + 1) * 30
            logger.warning("Router rate limit, retry %d/3 через %dс", attempt + 1, wait)
            if attempt < 2:
                await asyncio.sleep(wait)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Router fallback (error: %s), загружаем всё", e)
            break
    return {"sheets": [], "need_bitrix": True, "bitrix_data": ["deals", "pipeline_stats"]}


async def _gather_context(route: dict) -> str:
    """Собирает данные из кэша по маршруту."""
    parts: list[str] = []

    # Google Sheets данные
    if route.get("sheets"):
        for item in route["sheets"]:
            spreadsheet = item.get("spreadsheet", "")
            sheet = item.get("sheet", "")
            rows = await get_sheet_data(spreadsheet, sheet)
            if rows:
                parts.append(table_to_text(f"{spreadsheet} / {sheet}", rows))
    else:
        # Если маршрутизатор не указал конкретные листы — грузим всё из кэша
        all_data = await get_all_sheets_data()
        for spreadsheet_name, sheets in all_data.items():
            parts.append(spreadsheet_to_text(spreadsheet_name, sheets, max_rows_per_sheet=100))

    # Bitrix24 данные
    if route.get("need_bitrix"):
        for data_type in route.get("bitrix_data", []):
            if data_type == "debitors":
                # Дебиторы хранятся отдельно — формируем из deals
                deals = await get_bitrix_data("deals")
                if deals:
                    from bitrix.parser import debitors_to_text
                    debitor_deals = [d for d in deals if float(d.get("UF_CRM_1760524188", 0) or 0) > 0]
                    parts.append(debitors_to_text(debitor_deals))
            elif data_type == "overdue":
                deals = await get_bitrix_data("deals")
                if deals:
                    from bitrix.parser import overdue_to_text
                    from datetime import datetime
                    today = datetime.now().date()
                    overdue = []
                    for d in deals:
                        deadline_str = d.get("UF_CRM_1760523441", "")
                        if deadline_str and d.get("STAGE_ID") not in {"WON", "LOSE", "APOLOGY", "1", "2", "3"}:
                            try:
                                deadline = datetime.fromisoformat(deadline_str.split("T")[0]).date()
                                if deadline < today:
                                    overdue.append(d)
                            except (ValueError, TypeError):
                                pass
                    parts.append(overdue_to_text(overdue))
            else:
                data = await get_bitrix_data(data_type)
                if data:
                    if data_type == "deals":
                        from bitrix.parser import deals_summary_to_text
                        parts.append(deals_summary_to_text(data, "последние 90 дней"))
                    elif data_type == "pipeline_stats":
                        from bitrix.parser import pipeline_to_text
                        parts.append(pipeline_to_text(data))
                    elif data_type == "users":
                        deals = await get_bitrix_data("deals")
                        if deals:
                            from bitrix.parser import managers_to_text
                            parts.append(managers_to_text(deals, data))

    return "\n\n---\n\n".join(parts) if parts else "Нет данных в кэше. Попробуйте позже."


async def ask(question: str, data_context: str | None = None) -> str:
    """Основной метод: двухэтапный ИИ.

    Если data_context передан — используем его напрямую (совместимость).
    Если нет — маршрутизируем и собираем из кэша.
    """
    if data_context is None:
        # Двухэтапный режим
        route = await route_question(question)
        logger.info("Маршрут: %s", json.dumps(route, ensure_ascii=False)[:200])
        data_context = await _gather_context(route)

    client = get_client()

    user_message = f"""Данные из источников:

{data_context}

---

Вопрос: {question}"""

    for attempt in range(3):
        try:
            response = await client.messages.create(
                model=config.AI_MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text
        except anthropic.RateLimitError:
            wait = (attempt + 1) * 30
            logger.warning("Rate limit, retry %d/3 через %dс", attempt + 1, wait)
            if attempt < 2:
                await asyncio.sleep(wait)
            else:
                return "⏳ Сервер ИИ перегружен. Подожди 1-2 минуты и попробуй ещё раз."
        except anthropic.APIError as e:
            logger.error("Claude API error: %s", e)
            return f"Ошибка при обращении к ИИ: {e}"


async def generate_daily_report() -> str:
    """Генерирует утреннюю сводку из всех данных."""
    # Для ежедневного отчёта грузим всё
    route = {
        "sheets": [],  # все
        "need_bitrix": True,
        "bitrix_data": ["deals", "pipeline_stats", "users", "debitors", "overdue"],
    }
    context = await _gather_context(route)

    # Добавляем предрассчитанные метрики
    deals = await get_bitrix_data("deals")
    users = await get_bitrix_data("users")
    if deals:
        from analytics.metrics import (
            calculate_monthly_trend,
            calculate_avg_deal_cycle,
        )
        context += "\n\n---\n\n" + calculate_monthly_trend(deals)
        context += "\n\n" + calculate_avg_deal_cycle(deals)

    return await ask(DAILY_REPORT_PROMPT, context)


async def generate_weekly_report() -> str:
    """Генерирует еженедельный отчёт."""
    route = {
        "sheets": [],
        "need_bitrix": True,
        "bitrix_data": ["deals", "pipeline_stats", "users", "debitors", "overdue"],
    }
    context = await _gather_context(route)

    deals = await get_bitrix_data("deals")
    users = await get_bitrix_data("users")
    if deals:
        from analytics.metrics import (
            calculate_monthly_trend,
            calculate_manager_ranking,
            calculate_source_analysis,
            calculate_repeat_clients,
            calculate_avg_deal_cycle,
        )
        context += "\n\n---\n\n" + calculate_monthly_trend(deals)
        context += "\n\n" + calculate_avg_deal_cycle(deals)
        context += "\n\n" + calculate_source_analysis(deals)
        context += "\n\n" + calculate_repeat_clients(deals)
        if users:
            context += "\n\n" + calculate_manager_ranking(deals, users)

    # Загрузка производства
    all_sheets = await get_all_sheets_data()
    if all_sheets:
        from analytics.metrics import calculate_production_load
        context += "\n\n" + calculate_production_load(all_sheets)

    return await ask(WEEKLY_REPORT_PROMPT, context)
