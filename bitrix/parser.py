"""Конвертация данных Bitrix24 в текст для Claude."""

from __future__ import annotations

from datetime import datetime

from bitrix.client import STAGE_NAMES, ACTIVE_STAGES, LOST_STAGES


def deals_summary_to_text(deals: list[dict], period_label: str = "за период") -> str:
    """Краткая сводка сделок для Claude."""
    if not deals:
        return f"Сделки {period_label}: нет данных"

    total = len(deals)
    won = [d for d in deals if d.get("STAGE_ID") == "WON"]
    lost = [d for d in deals if d.get("STAGE_ID") in LOST_STAGES]
    active = [d for d in deals if d.get("STAGE_ID") in ACTIVE_STAGES]

    won_amount = sum(float(d.get("OPPORTUNITY", 0) or 0) for d in won)
    active_amount = sum(float(d.get("OPPORTUNITY", 0) or 0) for d in active)

    lines = [
        f"## Сделки Bitrix24 ({period_label})",
        f"Всего: {total} | Выиграно: {len(won)} | В работе: {len(active)} | Проиграно: {len(lost)}",
        f"Сумма выигранных: {won_amount:,.0f} сом",
        f"Сумма в работе: {active_amount:,.0f} сом",
    ]

    if won:
        avg_check = won_amount / len(won)
        lines.append(f"Средний чек (WON): {avg_check:,.0f} сом")

    if total:
        conv = len(won) / total * 100
        lines.append(f"Конверсия: {conv:.1f}%")

    return "\n".join(lines)


def pipeline_to_text(stats: dict) -> str:
    """Воронка продаж в текстовом формате."""
    lines = [
        "## Воронка продаж (последние 90 дней)",
        f"Всего сделок: {stats['total_deals']} | Конверсия: {stats['conversion_rate']}% | Средний чек: {stats['avg_check']:,.0f} сом",
        "---",
        "Стадия | Кол-во | Сумма",
    ]

    for stage_id in ["NEW", "PREPARATION", "PREPAYMENT_INVOICE", "UC_ZGID52",
                     "EXECUTING", "UC_LGY0S7", "FINAL_INVOICE", "WON",
                     "LOSE", "APOLOGY", "1", "2", "3"]:
        s = stats["stages"].get(stage_id, {})
        if s.get("count", 0) > 0:
            lines.append(f"{s['name']}: {s['count']} шт. | {s['total_amount']:,.0f} сом")

    return "\n".join(lines)


def debitors_to_text(deals: list[dict]) -> str:
    """Дебиторская задолженность."""
    if not deals:
        return "## Дебиторка\nНет задолженностей"

    total_debt = sum(float(d.get("UF_CRM_1760524188", 0) or 0) for d in deals)
    lines = [
        f"## Дебиторская задолженность",
        f"Всего: {total_debt:,.0f} сом ({len(deals)} сделок)",
        "---",
    ]

    for d in deals[:20]:
        debt = float(d.get("UF_CRM_1760524188", 0) or 0)
        stage = STAGE_NAMES.get(d.get("STAGE_ID", ""), d.get("STAGE_ID", ""))
        lines.append(f"- {d.get('TITLE', '?')}: {debt:,.0f} сом | {stage}")

    return "\n".join(lines)


def overdue_to_text(deals: list[dict]) -> str:
    """Просроченные заказы."""
    if not deals:
        return "## Просрочки\nНет просроченных заказов"

    lines = [
        f"## Просроченные заказы ({len(deals)} шт.)",
        "---",
    ]

    today = datetime.now().date()
    for d in deals:
        deadline_str = d.get("UF_CRM_1760523441", "")
        if deadline_str:
            try:
                deadline = datetime.fromisoformat(deadline_str.replace("+03:00", "")).date()
                days_late = (today - deadline).days
            except (ValueError, TypeError):
                days_late = 0
        else:
            days_late = 0

        stage = STAGE_NAMES.get(d.get("STAGE_ID", ""), d.get("STAGE_ID", ""))
        amount = float(d.get("OPPORTUNITY", 0) or 0)
        lines.append(
            f"- {d.get('TITLE', '?')}: {amount:,.0f} сом | {stage} | просрочка {days_late} дн."
        )

    return "\n".join(lines)


def managers_to_text(deals: list[dict], users: list[dict]) -> str:
    """Эффективность менеджеров."""
    user_map = {str(u["ID"]): f"{u.get('NAME', '')} {u.get('LAST_NAME', '')}".strip() for u in users}

    by_manager: dict[str, dict] = {}
    for d in deals:
        mid = str(d.get("ASSIGNED_BY_ID", ""))
        if mid not in by_manager:
            by_manager[mid] = {"name": user_map.get(mid, f"ID:{mid}"), "total": 0, "won": 0, "won_amount": 0}

        by_manager[mid]["total"] += 1
        if d.get("STAGE_ID") == "WON":
            by_manager[mid]["won"] += 1
            by_manager[mid]["won_amount"] += float(d.get("OPPORTUNITY", 0) or 0)

    lines = ["## Эффективность менеджеров (последние 90 дней)", "---"]

    for m in sorted(by_manager.values(), key=lambda x: x["won_amount"], reverse=True):
        conv = round(m["won"] / m["total"] * 100, 1) if m["total"] else 0
        avg = round(m["won_amount"] / m["won"]) if m["won"] else 0
        lines.append(
            f"- {m['name']}: {m['total']} сделок | {m['won']} выиграно ({conv}%) | "
            f"сумма {m['won_amount']:,.0f} сом | ср.чек {avg:,.0f}"
        )

    return "\n".join(lines)


def sources_to_text(deals: list[dict]) -> str:
    """Анализ источников клиентов."""
    by_source: dict[str, dict] = {}
    for d in deals:
        src = d.get("SOURCE_ID") or "Не указан"
        if src not in by_source:
            by_source[src] = {"total": 0, "won": 0, "won_amount": 0}
        by_source[src]["total"] += 1
        if d.get("STAGE_ID") == "WON":
            by_source[src]["won"] += 1
            by_source[src]["won_amount"] += float(d.get("OPPORTUNITY", 0) or 0)

    lines = ["## Источники клиентов (последние 90 дней)", "---"]
    for src, s in sorted(by_source.items(), key=lambda x: x[1]["won_amount"], reverse=True):
        conv = round(s["won"] / s["total"] * 100, 1) if s["total"] else 0
        lines.append(f"- {src}: {s['total']} сделок | {s['won']} выиграно ({conv}%) | {s['won_amount']:,.0f} сом")

    return "\n".join(lines)
