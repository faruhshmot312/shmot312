"""Планировщик задач: кэш, утренняя сводка, алерты."""

from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import config

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_bot = None


def setup_scheduler(bot) -> AsyncIOScheduler:
    """Настраивает и возвращает планировщик."""
    global _scheduler, _bot
    _bot = bot
    _scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)

    # Обновление кэша каждые 15 минут
    _scheduler.add_job(
        _refresh_cache_job,
        IntervalTrigger(minutes=config.CACHE_TTL_MINUTES),
        id="refresh_cache",
        name="Обновление кэша",
        replace_existing=True,
    )

    # Утренняя сводка — пн-сб в 9:00, в понедельник — еженедельная
    _scheduler.add_job(
        _daily_report_job,
        CronTrigger(hour=config.DAILY_REPORT_HOUR, minute=config.DAILY_REPORT_MINUTE, day_of_week="tue-sat"),
        id="daily_report",
        name="Утренняя сводка",
        replace_existing=True,
    )

    # Еженедельный отчёт — понедельник в 9:00
    _scheduler.add_job(
        _weekly_report_job,
        CronTrigger(hour=config.DAILY_REPORT_HOUR, minute=config.DAILY_REPORT_MINUTE, day_of_week="mon"),
        id="weekly_report",
        name="Еженедельный отчёт",
        replace_existing=True,
    )

    return _scheduler


async def _refresh_cache_job():
    """Обновляет кэш и проверяет алерты."""
    try:
        from cache.manager import refresh_all
        await refresh_all()
        logger.info("Кэш обновлён по расписанию")

        # Проверяем алерты после обновления
        await _check_alerts()
    except Exception as e:
        logger.error("Ошибка обновления кэша: %s", e)


async def _daily_report_job():
    """Отправляет утреннюю сводку."""
    try:
        from ai.engine import generate_daily_report
        report = await generate_daily_report()
        await _send_message(report)
        logger.info("Утренняя сводка отправлена")
    except Exception as e:
        logger.error("Ошибка утренней сводки: %s", e)


async def _weekly_report_job():
    """Отправляет еженедельный отчёт."""
    try:
        from ai.engine import generate_weekly_report
        report = await generate_weekly_report()
        await _send_message(report)
        logger.info("Еженедельный отчёт отправлен")
    except Exception as e:
        logger.error("Ошибка еженедельного отчёта: %s", e)


async def _check_alerts():
    """Проверяет пороговые значения и отправляет алерты."""
    try:
        from alerts import check_all_alerts
        messages = await check_all_alerts()
        for msg in messages:
            await _send_message(msg)
    except Exception as e:
        logger.error("Ошибка проверки алертов: %s", e)


async def _send_message(text: str):
    """Отправляет сообщение Фаруху с безопасным Markdown."""
    if not _bot or not config.ADMIN_CHAT_ID:
        return

    # Разбиваем на части если длинное
    chunks = [text[i:i + 4096] for i in range(0, len(text), 4096)]
    for chunk in chunks:
        try:
            await _bot.send_message(config.ADMIN_CHAT_ID, chunk, parse_mode="Markdown")
        except Exception:
            # Если Markdown упал — отправляем без форматирования
            try:
                await _bot.send_message(config.ADMIN_CHAT_ID, chunk)
            except Exception as e:
                logger.error("Не удалось отправить сообщение: %s", e)
