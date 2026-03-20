"""Расчёт бизнес-метрик из кэшированных данных."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime


def calculate_pipeline_conversion(deals: list[dict]) -> str:
    """Конверсия по этапам воронки продаж."""
    from bitrix.client import STAGE_NAMES

    stages_order = [
        "NEW", "PREPARATION", "PREPAYMENT_INVOICE", "UC_ZGID52",
        "EXECUTING", "UC_LGY0S7", "FINAL_INVOICE", "WON",
    ]

    total = len(deals)
    if not total:
        return "Нет данных по воронке"

    lines = ["## Конверсия воронки (пошагово)", f"Всего входящих: {total}", "---"]

    prev_count = total
    for stage_id in stages_order:
        # Считаем сколько сделок дошли до этой стадии или дальше
        idx = stages_order.index(stage_id)
        reached = [d for d in deals if d.get("STAGE_ID") in stages_order[idx:]]
        count = len(reached)
        rate = round(count / prev_count * 100, 1) if prev_count else 0
        name = STAGE_NAMES.get(stage_id, stage_id)
        lines.append(f"{name}: {count} ({rate}% от предыдущего)")
        prev_count = count if count else prev_count

    return "\n".join(lines)


def calculate_avg_deal_cycle(deals: list[dict]) -> str:
    """Средний цикл сделки (дни от создания до закрытия)."""
    cycles = []
    for d in deals:
        if d.get("STAGE_ID") != "WON":
            continue
        created = d.get("DATE_CREATE", "")
        closed = d.get("CLOSEDATE", "")
        if not created or not closed:
            continue
        try:
            dt_created = datetime.fromisoformat(created.replace("+03:00", "+03:00"))
            dt_closed = datetime.fromisoformat(closed.replace("+03:00", "+03:00"))
            days = (dt_closed - dt_created).days
            if 0 <= days < 365:
                cycles.append(days)
        except (ValueError, TypeError):
            continue

    if not cycles:
        return "Средний цикл сделки: нет данных"

    avg = sum(cycles) / len(cycles)
    mn = min(cycles)
    mx = max(cycles)
    return f"Средний цикл сделки: {avg:.0f} дней (мин: {mn}, макс: {mx}, выборка: {len(cycles)})"


def calculate_manager_ranking(deals: list[dict], users: list[dict]) -> str:
    """Ранжирование менеджеров по эффективности."""
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

    lines = ["## Рейтинг менеджеров", "---"]
    ranked = sorted(by_manager.values(), key=lambda x: x["revenue"], reverse=True)
    for i, m in enumerate(ranked, 1):
        conv = round(m["won"] / m["total"] * 100, 1) if m["total"] else 0
        avg_check = round(m["revenue"] / m["won"]) if m["won"] else 0
        lines.append(
            f"{i}. {m['name']}: выручка {m['revenue']:,.0f} | "
            f"сделок {m['total']} | выиграно {m['won']} ({conv}%) | ср.чек {avg_check:,.0f}"
        )

    return "\n".join(lines)


def calculate_source_analysis(deals: list[dict]) -> str:
    """Анализ источников: конверсия и средний чек по каждому."""
    by_source: dict[str, dict] = {}
    for d in deals:
        src = d.get("SOURCE_ID") or "Не указан"
        if src not in by_source:
            by_source[src] = {"total": 0, "won": 0, "revenue": 0}
        by_source[src]["total"] += 1
        if d.get("STAGE_ID") == "WON":
            by_source[src]["won"] += 1
            by_source[src]["revenue"] += float(d.get("OPPORTUNITY", 0) or 0)

    lines = ["## Анализ источников клиентов", "---"]
    for src, s in sorted(by_source.items(), key=lambda x: x[1]["revenue"], reverse=True):
        conv = round(s["won"] / s["total"] * 100, 1) if s["total"] else 0
        avg = round(s["revenue"] / s["won"]) if s["won"] else 0
        lines.append(f"- {src}: {s['total']} лидов → {s['won']} сделок ({conv}%) | выручка {s['revenue']:,.0f} | ср.чек {avg:,.0f}")

    return "\n".join(lines)


def calculate_repeat_clients(deals: list[dict]) -> str:
    """LTV и повторные клиенты."""
    by_contact: dict[str, list[dict]] = defaultdict(list)
    for d in deals:
        cid = d.get("CONTACT_ID")
        if cid and d.get("STAGE_ID") == "WON":
            by_contact[cid].append(d)

    total_clients = len(by_contact)
    repeat = {k: v for k, v in by_contact.items() if len(v) > 1}
    repeat_count = len(repeat)

    if not total_clients:
        return "## LTV клиентов\nНет данных"

    repeat_pct = round(repeat_count / total_clients * 100, 1)

    all_revenue = sum(float(d.get("OPPORTUNITY", 0) or 0) for deals_list in by_contact.values() for d in deals_list)
    avg_ltv = round(all_revenue / total_clients) if total_clients else 0

    repeat_revenue = sum(float(d.get("OPPORTUNITY", 0) or 0) for deals_list in repeat.values() for d in deals_list)

    lines = [
        "## LTV и повторные клиенты",
        f"Уникальных клиентов: {total_clients}",
        f"Повторные: {repeat_count} ({repeat_pct}%)",
        f"Средний LTV: {avg_ltv:,.0f} сом",
        f"Выручка от повторных: {repeat_revenue:,.0f} сом",
    ]

    # Топ-5 клиентов по LTV
    top_clients = sorted(by_contact.items(), key=lambda x: sum(float(d.get("OPPORTUNITY", 0) or 0) for d in x[1]), reverse=True)[:5]
    if top_clients:
        lines.append("---")
        lines.append("Топ-5 клиентов по LTV:")
        for cid, client_deals in top_clients:
            revenue = sum(float(d.get("OPPORTUNITY", 0) or 0) for d in client_deals)
            name = client_deals[0].get("TITLE", f"Контакт {cid}")
            lines.append(f"- {name}: {revenue:,.0f} сом ({len(client_deals)} заказов)")

    return "\n".join(lines)


def calculate_monthly_trend(deals: list[dict]) -> str:
    """Помесячный тренд выручки для прогнозирования."""
    by_month: dict[str, dict] = {}
    for d in deals:
        if d.get("STAGE_ID") != "WON":
            continue
        date_str = d.get("DATE_CREATE", "")
        if not date_str:
            continue
        try:
            dt = datetime.fromisoformat(date_str.replace("+03:00", "+03:00"))
            key = dt.strftime("%Y-%m")
        except (ValueError, TypeError):
            continue

        if key not in by_month:
            by_month[key] = {"count": 0, "revenue": 0}
        by_month[key]["count"] += 1
        by_month[key]["revenue"] += float(d.get("OPPORTUNITY", 0) or 0)

    if not by_month:
        return "## Тренд выручки\nНет данных"

    lines = ["## Помесячный тренд выручки (выигранные сделки)", "---"]
    for month in sorted(by_month.keys()):
        m = by_month[month]
        avg = round(m["revenue"] / m["count"]) if m["count"] else 0
        lines.append(f"{month}: {m['count']} сделок | {m['revenue']:,.0f} сом | ср.чек {avg:,.0f}")

    # Простой прогноз — среднее за последние 3 месяца
    recent = sorted(by_month.keys())[-3:]
    if len(recent) >= 2:
        recent_avg = sum(by_month[m]["revenue"] for m in recent) / len(recent)
        lines.append(f"---")
        lines.append(f"Прогноз (среднее за {len(recent)} мес.): ~{recent_avg:,.0f} сом/мес")

    return "\n".join(lines)


def calculate_production_load(sheets_data: dict[str, dict[str, list[list[str]]]]) -> str:
    """Загрузка менеджеров — данные по таблицам."""
    seamstress_tables = ["Сайкал | SHMOT312", "Алтынай | MyStyle", "Абубакир", "Гульнара"]

    lines = ["## Загрузка менеджеров", "---"]

    for name in seamstress_tables:
        if name not in sheets_data:
            continue

        total_orders = 0
        for sheet_name, rows in sheets_data[name].items():
            if "Сводная" in sheet_name:
                # Сводная содержит итоги
                continue
            if "Статистика" in sheet_name or "Вышивка" in sheet_name:
                continue
            # Месячные листы содержат заказы
            total_orders += max(0, len(rows) - 1)  # минус заголовок

        lines.append(f"- {name}: {total_orders} записей в месячных листах")

    return "\n".join(lines)
