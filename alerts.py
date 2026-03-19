"""Система алертов — проверка пороговых значений и уведомления."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from cache.db import get_db
from cache.manager import get_bitrix_data, get_all_sheets_data
from config import config

logger = logging.getLogger(__name__)


async def check_all_alerts() -> list[str]:
    """Проверяет все условия алертов. Возвращает список сообщений."""
    messages: list[str] = []

    # 1. Дебиторка
    deals = await get_bitrix_data("deals")
    if deals:
        debitor_alerts = await _check_debitors(deals)
        messages.extend(debitor_alerts)

        overdue_alerts = await _check_overdue(deals)
        messages.extend(overdue_alerts)

        order_alerts = await _check_low_orders(deals)
        messages.extend(order_alerts)

    return messages


async def _already_sent(alert_key: str, hours: int = 24) -> bool:
    """Проверяет, отправлялся ли алерт за последние N часов."""
    db = await get_db()
    try:
        since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM alerts_sent WHERE alert_key=? AND sent_at > ?",
            (alert_key, since),
        )
        row = await cursor.fetchone()
        return row["cnt"] > 0 if row else False
    finally:
        await db.close()


async def _mark_sent(alert_key: str, message: str):
    """Записывает отправленный алерт."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO alerts_sent (alert_key, message) VALUES (?, ?)",
            (alert_key, message),
        )
        await db.commit()
    finally:
        await db.close()


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
    today = datetime.now().date()
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
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_deals = [
        d for d in deals
        if d.get("DATE_CREATE", "").startswith(today_str)
    ]

    # Проверяем только после 18:00
    if datetime.now().hour < 18:
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
