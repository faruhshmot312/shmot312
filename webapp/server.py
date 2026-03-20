"""FastAPI сервер для Telegram WebApp дашборда."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from cache.manager import get_all_sheets_data, get_bitrix_data

logger = logging.getLogger(__name__)

_TZ = timezone(timedelta(hours=6))  # Asia/Bishkek

app = FastAPI(title="Шмот312 Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _parse_number(value: str) -> float:
    """Парсит число: '1 161 460,51' → 1161460.51"""
    if not value:
        return 0.0
    cleaned = value.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/dashboard")
async def dashboard():
    """Главный экран — ключевые показатели."""
    all_data = await get_all_sheets_data()
    deals = await get_bitrix_data("deals") or []
    users = await get_bitrix_data("users") or []
    pipeline = await get_bitrix_data("pipeline_stats") or {}

    # --- Баланс ---
    bank = all_data.get("Банк Компании", {})
    bank_sheet = bank.get("Банк | 2026", [])
    balance = _parse_number(bank_sheet[0][3]) if bank_sheet and len(bank_sheet[0]) > 3 else 0

    cash_sheet = bank.get("Наличные", [])
    cash = _parse_number(cash_sheet[0][3]) if cash_sheet and len(cash_sheet[0]) > 3 else 0

    # --- Постоянные расходы ---
    costs_sheet = bank.get("Постоянные затраты", [])
    monthly_costs = _parse_number(costs_sheet[1][1]) if costs_sheet and len(costs_sheet) > 1 and len(costs_sheet[1]) > 1 else 0

    # --- Банк статистика (помесячно) ---
    bank_stats = bank.get("Банк | Статистика", [])
    months_data = []
    for row in bank_stats[1:]:  # skip header
        if row and row[0] and row[0].strip():
            months_data.append({
                "month": row[0],
                "income": _parse_number(row[1]) if len(row) > 1 else 0,
                "expense": _parse_number(row[3]) if len(row) > 3 else 0,
                "saldo": _parse_number(row[5]) if len(row) > 5 else 0,
                "balance": _parse_number(row[7]) if len(row) > 7 else 0,
            })

    # --- Сделки Bitrix ---
    won = [d for d in deals if d.get("STAGE_ID") == "WON"]
    active = [d for d in deals if d.get("STAGE_ID") in {"NEW", "PREPARATION", "PREPAYMENT_INVOICE", "UC_ZGID52", "EXECUTING", "UC_LGY0S7", "FINAL_INVOICE"}]
    lost_stages = {"LOSE", "APOLOGY", "1", "2", "3"}
    lost = [d for d in deals if d.get("STAGE_ID") in lost_stages]

    won_amount = sum(float(d.get("OPPORTUNITY", 0) or 0) for d in won)
    active_amount = sum(float(d.get("OPPORTUNITY", 0) or 0) for d in active)
    avg_check = won_amount / len(won) if won else 0
    conversion = len(won) / len(deals) * 100 if deals else 0

    # --- Дебиторка ---
    debitors = [d for d in deals if float(d.get("UF_CRM_1760524188", 0) or 0) > 0]
    total_debt = sum(float(d.get("UF_CRM_1760524188", 0) or 0) for d in debitors)
    debitor_list = []
    for d in sorted(debitors, key=lambda x: float(x.get("UF_CRM_1760524188", 0) or 0), reverse=True)[:15]:
        debitor_list.append({
            "title": d.get("TITLE", "?"),
            "debt": float(d.get("UF_CRM_1760524188", 0) or 0),
            "stage": d.get("STAGE_ID", "?"),
        })

    # --- Воронка ---
    from bitrix.client import STAGE_NAMES
    funnel = []
    if pipeline and "stages" in pipeline:
        stage_order = ["NEW", "PREPARATION", "PREPAYMENT_INVOICE", "UC_ZGID52", "EXECUTING", "UC_LGY0S7", "FINAL_INVOICE", "WON"]
        for sid in stage_order:
            s = pipeline["stages"].get(sid, {})
            if s.get("count", 0) > 0:
                funnel.append({
                    "stage": s.get("name", sid),
                    "count": s["count"],
                    "amount": s.get("total_amount", 0),
                })

    # --- Прибыль ---
    # Выручка из "Итоговые"
    report = all_data.get("Общий отчёт по заказам | 2026", {})
    totals_sheet = report.get("Итоговые", [])
    total_orders_sum = _parse_number(totals_sheet[1][1]) if len(totals_sheet) > 1 and len(totals_sheet[1]) > 1 else 0
    total_paid = _parse_number(totals_sheet[7][1]) if len(totals_sheet) > 7 and len(totals_sheet[7]) > 1 else 0
    total_unpaid = _parse_number(totals_sheet[8][1]) if len(totals_sheet) > 8 and len(totals_sheet[8]) > 1 else 0

    # Закуп из "закупки | 2026" — помесячные итоги
    purchase = all_data.get("Закуп | 2026", {})
    purchase_sheet = purchase.get("закупки | 2026", [])
    monthly_purchases = []
    total_purchases = 0.0
    month_names_map = {
        "ЯНВАРЬ": "Январь", "ФЕВРАЛЬ": "Февраль", "МАРТ": "Март",
        "АПРЕЛЬ": "Апрель", "МАЙ": "Май", "ИЮНЬ": "Июнь",
        "ИЮЛЬ": "Июль", "АВГУСТ": "Август", "СЕНТЯБРЬ": "Сентябрь",
        "ОКТЯБРЬ": "Октябрь", "НОЯБРЬ": "Ноябрь", "ДЕКАБРЬ": "Декабрь",
    }
    for row in purchase_sheet:
        if row and row[0] and "| 2026" in row[0] and len(row) > 2:
            raw_month = row[0].split("|")[0].strip()
            month_label = month_names_map.get(raw_month, raw_month)
            amount = _parse_number(row[2])
            if amount > 0:
                monthly_purchases.append({"month": month_label, "amount": amount})
                total_purchases += amount

    # Помесячная прибыль (из Банк Статистика: сальдо = приход − расход)
    monthly_profit = []
    total_income_ytd = 0.0
    total_expense_ytd = 0.0
    for md in months_data:
        total_income_ytd += md["income"]
        total_expense_ytd += md["expense"]
        monthly_profit.append({
            "month": md["month"],
            "income": md["income"],
            "expense": md["expense"],
            "profit": md["saldo"],
        })

    net_profit_ytd = total_income_ytd - total_expense_ytd
    months_elapsed = max(len(months_data), 1)
    gross_margin = round((total_paid - total_purchases) / total_paid * 100, 1) if total_paid > 0 else 0

    # --- Менеджеры (таблицы) ---
    seamstresses = []
    for name in ["Сайкал | SHMOT312", "Алтынай | MyStyle", "Абубакир", "Гульнара"]:
        ss_data = all_data.get(name, {})
        summary = ss_data.get("Сводная за 2026 год", [])
        if summary and len(summary) > 0:
            total_sum = _parse_number(summary[0][1]) if len(summary[0]) > 1 else 0
            paid = _parse_number(summary[1][1]) if len(summary) > 1 and len(summary[1]) > 1 else 0
            # Count monthly sheets for order count
            order_count = 0
            for sheet_name, rows in ss_data.items():
                if "Сводная" in sheet_name or "Статистика" in sheet_name or "Вышивка" in sheet_name:
                    continue
                order_count += max(0, len(rows) - 5)  # minus headers

            display_name = name.split(" | ")[0]
            seamstresses.append({
                "name": display_name,
                "total": total_sum,
                "paid": paid,
                "orders": order_count,
            })

    # --- Менеджеры ---
    user_map = {str(u["ID"]): f"{u.get('NAME', '')} {u.get('LAST_NAME', '')}".strip() for u in users}
    by_manager: dict[str, dict] = {}
    for d in deals:
        mid = str(d.get("ASSIGNED_BY_ID", ""))
        if mid not in by_manager:
            by_manager[mid] = {"name": user_map.get(mid, f"ID:{mid}"), "total": 0, "won": 0, "revenue": 0}
        by_manager[mid]["total"] += 1
        if d.get("STAGE_ID") == "WON":
            by_manager[mid]["won"] += 1
            by_manager[mid]["revenue"] += float(d.get("OPPORTUNITY", 0) or 0)

    managers = []
    for m in sorted(by_manager.values(), key=lambda x: x["revenue"], reverse=True):
        conv = round(m["won"] / m["total"] * 100, 1) if m["total"] else 0
        avg = round(m["revenue"] / m["won"]) if m["won"] else 0
        managers.append({
            "name": m["name"],
            "total": m["total"],
            "won": m["won"],
            "revenue": m["revenue"],
            "conversion": conv,
            "avg_check": avg,
        })

    # --- Просрочки ---
    today = datetime.now(_TZ).date()
    overdue = []
    for d in deals:
        if d.get("STAGE_ID") in lost_stages or d.get("STAGE_ID") == "WON":
            continue
        deadline_str = d.get("UF_CRM_1760523441", "")
        if not deadline_str:
            continue
        try:
            deadline = datetime.fromisoformat(deadline_str.split("T")[0]).date()
            days_late = (today - deadline).days
            if days_late > 0:
                overdue.append({
                    "title": d.get("TITLE", "?"),
                    "deadline": deadline.strftime("%d.%m.%Y"),
                    "days_late": days_late,
                    "amount": float(d.get("OPPORTUNITY", 0) or 0),
                })
        except (ValueError, TypeError):
            continue

    # --- Анализ отказов ---
    rejection_reasons = {}
    rejection_names = {"LOSE": "Пропал/не отвечает", "APOLOGY": "Дорого/бюджет", "1": "Не сможем отшить", "2": "Своя вещь розница", "3": "Дубликат"}
    for d in lost:
        stage = d.get("STAGE_ID", "?")
        name = rejection_names.get(stage, stage)
        rejection_reasons[name] = rejection_reasons.get(name, 0) + 1

    days_left = (balance + cash) / (monthly_costs / 30) if monthly_costs > 0 else 999

    return {
        "finance": {
            "bank_balance": balance,
            "cash": cash,
            "total": balance + cash,
            "monthly_costs": monthly_costs,
            "days_left": round(days_left, 1),
            "months_data": months_data,
        },
        "profit": {
            "total_orders": total_orders_sum,
            "total_paid": total_paid,
            "total_unpaid": total_unpaid,
            "total_purchases": total_purchases,
            "fixed_costs_monthly": monthly_costs,
            "net_profit_ytd": net_profit_ytd,
            "total_income_ytd": total_income_ytd,
            "total_expense_ytd": total_expense_ytd,
            "gross_margin": gross_margin,
            "monthly_purchases": monthly_purchases,
            "monthly_profit": monthly_profit,
        },
        "deals": {
            "total": len(deals),
            "won": len(won),
            "active": len(active),
            "lost": len(lost),
            "won_amount": won_amount,
            "active_amount": active_amount,
            "avg_check": round(avg_check),
            "conversion": round(conversion, 1),
        },
        "funnel": funnel,
        "debitors": {"total": total_debt, "count": len(debitors), "list": debitor_list},
        "overdue": sorted(overdue, key=lambda x: x["days_late"], reverse=True)[:10],
        "managers_sheets": seamstresses,
        "managers": managers,
        "rejections": rejection_reasons,
    }
