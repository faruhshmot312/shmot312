"""Bitrix24 REST API клиент."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin

import httpx

from config import config

logger = logging.getLogger(__name__)

# Воронка продаж Шмот312
STAGE_NAMES = {
    "NEW": "Целевая заявка",
    "PREPARATION": "Предоплата получена",
    "PREPAYMENT_INVOICE": "Дизайн/Закуп",
    "UC_ZGID52": "Закрой/Цех",
    "EXECUTING": "Нанесение",
    "UC_LGY0S7": "ОТК",
    "FINAL_INVOICE": "Заказ готов",
    "WON": "Сделка успешна",
    "LOSE": "Пропал/не отвечает",
    "APOLOGY": "Дорого/бюджет",
    "1": "Не сможем отшить",
    "2": "Своя вещь розница",
    "3": "Дубликат сделки",
}

# Стадии «в работе» (активные)
ACTIVE_STAGES = {"NEW", "PREPARATION", "PREPAYMENT_INVOICE", "UC_ZGID52", "EXECUTING", "UC_LGY0S7", "FINAL_INVOICE"}
LOST_STAGES = {"LOSE", "APOLOGY", "1", "2", "3"}

# Поля сделки для запросов
DEAL_SELECT = [
    "ID", "TITLE", "STAGE_ID", "OPPORTUNITY", "CURRENCY_ID",
    "DATE_CREATE", "CLOSEDATE", "ASSIGNED_BY_ID", "CONTACT_ID",
    "COMPANY_ID", "SOURCE_ID",
    "UF_CRM_1760088070",   # Тип заказа
    "UF_CRM_1760088138",   # Тип нанесения
    "UF_CRM_1760523441",   # Срок заказа
    "UF_CRM_1760524107",   # Фактические оплаты
    "UF_CRM_1760524188",   # Остаток оплаты
    "UF_CRM_1760523257",   # DTF / Вышивка
    "UF_CRM_1761665423",   # Товары заказа
]


class BitrixClient:
    """Асинхронный клиент Bitrix24 REST API."""

    def __init__(self, webhook_url: str | None = None):
        self.base_url = (webhook_url or config.BITRIX24_WEBHOOK_URL).rstrip("/") + "/"

    async def _call(self, method: str, params: dict | None = None) -> dict:
        """Вызов метода Bitrix24 REST API."""
        url = urljoin(self.base_url, method)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=params or {})
            resp.raise_for_status()
            return resp.json()

    async def _call_list(self, method: str, params: dict | None = None, limit: int = 0) -> list[dict]:
        """Вызов метода с пагинацией — получает все записи."""
        params = dict(params or {})
        result = []
        start = 0

        while True:
            params["start"] = start
            data = await self._call(method, params)
            items = data.get("result", [])
            result.extend(items)

            next_start = data.get("next")
            if not next_start or (limit and len(result) >= limit):
                break
            start = next_start

        return result[:limit] if limit else result

    async def get_recent_deals(self, days: int = 90) -> list[dict]:
        """Получает сделки за последние N дней."""
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")
        params = {
            "filter": {">=DATE_CREATE": since},
            "select": DEAL_SELECT,
            "order": {"DATE_CREATE": "DESC"},
        }
        return await self._call_list("crm.deal.list", params)

    async def get_active_deals(self) -> list[dict]:
        """Получает все активные сделки (в работе)."""
        params = {
            "filter": {"STAGE_ID": list(ACTIVE_STAGES)},
            "select": DEAL_SELECT,
            "order": {"DATE_CREATE": "DESC"},
        }
        return await self._call_list("crm.deal.list", params)

    async def get_pipeline_stats(self) -> dict:
        """Считает статистику воронки продаж."""
        deals = await self.get_recent_deals(days=90)

        stats: dict[str, dict] = {}
        for stage_id, stage_name in STAGE_NAMES.items():
            stage_deals = [d for d in deals if d.get("STAGE_ID") == stage_id]
            total_amount = sum(float(d.get("OPPORTUNITY", 0) or 0) for d in stage_deals)
            stats[stage_id] = {
                "name": stage_name,
                "count": len(stage_deals),
                "total_amount": total_amount,
            }

        total = len(deals)
        won = stats.get("WON", {}).get("count", 0)

        return {
            "stages": stats,
            "total_deals": total,
            "won_deals": won,
            "conversion_rate": round(won / total * 100, 1) if total else 0,
            "avg_check": round(
                stats.get("WON", {}).get("total_amount", 0) / won, 0
            ) if won else 0,
            "period_days": 90,
        }

    async def get_users(self) -> list[dict]:
        """Получает список сотрудников."""
        data = await self._call("user.get", {"filter": {"ACTIVE": True}})
        return data.get("result", [])

    async def get_debitors(self) -> list[dict]:
        """Получает сделки с остатком оплаты > 0."""
        params = {
            "filter": {
                ">UF_CRM_1760524188": 0,
                "!STAGE_ID": list(LOST_STAGES),
            },
            "select": DEAL_SELECT,
            "order": {"UF_CRM_1760524188": "DESC"},
        }
        return await self._call_list("crm.deal.list", params)

    async def get_overdue_deals(self) -> list[dict]:
        """Получает просроченные сделки (срок прошёл, не закрыты)."""
        today = datetime.now().strftime("%Y-%m-%d")
        params = {
            "filter": {
                "<UF_CRM_1760523441": today,
                "STAGE_ID": list(ACTIVE_STAGES),
            },
            "select": DEAL_SELECT,
        }
        return await self._call_list("crm.deal.list", params)

    async def get_deals_by_date(self, date_from: str, date_to: str) -> list[dict]:
        """Получает сделки за период (YYYY-MM-DD)."""
        params = {
            "filter": {
                ">=DATE_CREATE": f"{date_from}T00:00:00",
                "<=DATE_CREATE": f"{date_to}T23:59:59",
            },
            "select": DEAL_SELECT,
            "order": {"DATE_CREATE": "DESC"},
        }
        return await self._call_list("crm.deal.list", params)
