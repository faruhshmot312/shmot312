"""Инициализация и запуск Telegram-бота."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from bot.handlers import router
from bot.middleware import AuthMiddleware
from config import config

logger = logging.getLogger(__name__)


def create_bot() -> tuple[Bot, Dispatcher]:
    """Создаёт и настраивает бота и диспетчер."""
    bot = Bot(
        token=config.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="Markdown"),
    )
    dp = Dispatcher()

    # Middleware авторизации
    dp.message.middleware(AuthMiddleware())

    # Подключаем хэндлеры
    dp.include_router(router)

    return bot, dp


async def start_bot() -> None:
    """Запускает polling бота с кэшем и планировщиком."""
    bot, dp = create_bot()

    # Начальная загрузка кэша
    logger.info("Загружаю данные в кэш...")
    try:
        from cache.manager import refresh_all
        await refresh_all()
        logger.info("Кэш загружен!")
    except Exception as e:
        logger.error("Ошибка загрузки кэша: %s", e)

    # Запускаем планировщик
    from scheduler import setup_scheduler
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Планировщик запущен: кэш каждые %d мин, сводка в %02d:%02d",
                config.CACHE_TTL_MINUTES, config.DAILY_REPORT_HOUR, config.DAILY_REPORT_MINUTE)

    logger.info("Бот запущен!")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()
