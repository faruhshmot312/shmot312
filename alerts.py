"""Система алертов — проверка пороговых значений и уведомления."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from cache.db import get_db
from cache.manager import get_bitrix_data, get_all_sheets_data
from config import config

logger = logging.getLogger(__name__)

# Таймзона бизнеса
_TZ = timezone(timedelta(hours=6))  # Asia/Bishkek = UTC+6


def _now() -> datetime:
    """Текущее время в таймзоне бизнеса."""
    return datetime.now(_TZ)


async def check_all_alerts() -> list[str]:
    """Проверяет все условия алертов. Возвращает список сообщений."""
    messages: list[str] = []

    # Bitrix-алерты
    deals = await get_bitrix_data("deals")
    if deals:
        messages.extend(await _check_debitors(deals))
        messages.extend(await _check_overdue(deals))
        messages.extend(await _check_low_orders(deals))

    # Финансовые алерты из Google Sheets
    messages.extend(await _check_cash_balance())

    return messages


async def _already_sent(alert_key: str, hours: int = 24) -> bool:
    """Проверяет, отправлялся ли алерт за последние N часов."""
    db = await get_db()
    since = (_now() - timedelta(hours=hours)).isoformat()
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM alerts_sent WHERE alert_key=? AND sent_at > ?",
        (alert_key, since),
    )
    row = await cursor.fetchone()
    return row["cnt"] > 0 if row else False


async def _mark_sent(alert_key: str, message: str):
    """Записывает отправленный алерт."""
    db = await get_db()
    await db.execute(
        "INSERT INTO alerts_sent (alert_key, message, sent_at) VALUES (?, ?, ?)",
        (alert_key, message, _now().isoformat()),
    )
    await db.commit()


def _parse_number(value: str) -> float:
    """Парсит число из таблицы: '1 161 460,51' → 1161460.51"""
    if not value:
        return 0.0
    cleaned = value.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


async def _check_cash_balance() -> list[str]:
    """Алерт: остаток на счету ниже порога."""
    messages = []
    all_data = await get_all_sheets_data()

    bank = all_data.get("Банк Компании", {})
    bank_sheet = bank.get("Банк | 2026", [])
    if not bank_sheet:
        return []

    # Баланс — строка 0, ячейка 3
    balance = _parse_number(bank_sheet[0][3]) if len(bank_sheet[0]) > 3 else 0

    # Наличные — баланс
    cash_sheet = bank.get("Наличные", [])
    cash = _parse_number(cash_sheet[0][3]) if cash_sheet and len(cash_sheet[0]) > 3 else 0

    total_cash = balance + cash

    if total_cash < config.ALERT_CASH_MIN:
        key = f"low_cash_{_now().strftime('%Y-%m-%d')}"
        if not await _already_sent(key):
            msg = (
                f"🔴 *Мало денег на счету*\n"
                f"Баланс банка: {balance:,.0f} сом\n"
                f"Наличные: {cash:,.0f} сом\n"
                f"Итого: {total_cash:,.0f} сом\n"
                f"Порог: {config.ALERT_CASH_MIN:,.0f} сом"
            )
            await _mark_sent(key, msg)
            messages.append(msg)

    # Прогноз кассового разрыва
    costs_sheet = bank.get("Постоянные затраты", [])
    if costs_sheet and len(costs_sheet) > 1:
        monthly_costs = _parse_number(costs_sheet[1][1]) if len(costs_sheet[1]) > 1 else 0
        if monthly_costs > 0:
            daily_costs = monthly_costs / 30
            days_left = total_cash / daily_costs if daily_costs > 0 else 999

            if days_left < 14:
                key = f"cash_gap_{_now().strftime('%Y-%m-%d')}"
                if not await _already_sent(key):
                    msg = (
                        f"⚠️ *Прогноз кассового разрыва*\n"
                        f"Денег хватит на: {days_left:.0f} дней\n"
                        f"Остаток: {total_cash:,.0f} сом\n"
                        f"Постоянные расходы: ~{monthly_costs:,.0f} сом/мес (~{daily_costs:,.0f}/день)"
                    )
                    await _mark_sent(key, msg)
                    messages.append(msg)

    return messages


async def _check_debitors(deals: list[dict]) -> list[str]:
    """Алерт: крупная дебиторка."""
    messages = []
    for d in deals:
        debt = float(d.get("UF_CRM_1760524188", 0) or 0)
        if debt >= config.ALERT_DEBT_MAX:
            key = f"debt_{d['ID']}"
            if not await _already_sent(key):
                msg = (
                    f"⚠️ *Дебиторка*\n"
                    f"Сделка: {d.get('TITLE', '?')}\n"
                    f"Остаток: {debt:,.0f} сом\n"
                    f"Стадия: {d.get('STAGE_ID', '?')}"
                )
                await _mark_sent(key, msg)
                messages.append(msg)
    return messages


async def _check_overdue(deals: list[dict]) -> list[str]:
    """Алерт: просроченные заказы."""
    messages = []
    today = _now().date()
    active_stages = {"NEW", "PREPARATION", "PREPAYMENT_INVOICE", "UC_ZGID52", "EXECUTING", "UC_LGY0S7", "FINAL_INVOICE"}

    for d in deals:
        if d.get("STAGE_ID") not in active_stages:
            continue
        deadline_str = d.get("UF_CRM_1760523441", "")
        if not deadline_str:
            continue
        try:
            deadline = datetime.fromisoformat(deadline_str.split("T")[0]).date()
        except (ValueError, TypeError):
            continue

        days_late = (today - deadline).days
        if days_late >= 3:
            key = f"overdue_{d['ID']}"
            if not await _already_sent(key):
                amount = float(d.get("OPPORTUNITY", 0) or 0)
                msg = (
                    f"🔴 *Просрочка*\n"
                    f"Сделка: {d.get('TITLE', '?')}\n"
                    f"Срок был: {deadline.strftime('%d.%m.%Y')} (просрочка {days_late} дн.)\n"
                    f"Сумма: {amount:,.0f} сом"
                )
                await _mark_sent(key, msg)
                messages.append(msg)
    return messages


async def _check_low_orders(deals: list[dict]) -> list[str]:
    """Алерт: аномально мало заказов за сегодня."""
    today_str = _now().strftime("%Y-%m-%d")
    today_deals = [
        d for d in deals
        if d.get("DATE_CREATE", "").startswith(today_str)
    ]

    # Проверяем только после 18:00
    if _now().hour < 18:
        return []

    if len(today_deals) < config.ALERT_ORDERS_MIN:
        key = f"low_orders_{today_str}"
        if not await _already_sent(key):
            msg = (
                f"📉 *Мало заказов сегодня*\n"
                f"Новых сделок за {today_str}: {len(today_deals)}\n"
                f"Норма: {config.ALERT_ORDERS_MIN}+"
            )
            await _mark_sent(key, msg)
            return [msg]

    return []
