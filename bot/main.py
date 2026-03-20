"""Инициализация и запуск Telegram-бота + WebApp сервера."""

from __future__ import annotations

import asyncio
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
    auth = AuthMiddleware()
    dp.message.middleware(auth)
    dp.callback_query.middleware(auth)

    # Подключаем хэндлеры
    dp.include_router(router)

    return bot, dp


async def start_webapp():
    """Запускает FastAPI сервер для WebApp."""
    import uvicorn
    from webapp.server import app

    uvicorn_config = uvicorn.Config(
        app,
        host=config.WEBAPP_HOST,
        port=config.WEBAPP_PORT,
        log_level="warning",
    )
    server = uvicorn.Server(uvicorn_config)
    await server.serve()


async def start_bot() -> None:
    """Запускает polling бота с кэшем, планировщиком и WebApp."""
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

    # Запускаем WebApp сервер в фоне
    webapp_task = asyncio.create_task(start_webapp())
    logger.info("WebApp сервер запущен на порту %d", config.WEBAPP_PORT)

    logger.info("Бот запущен!")
    try:
        await dp.start_polling(bot)
    finally:
        webapp_task.cancel()
        scheduler.shutdown()
        from cache.db import close_db
        await close_db()
        await bot.session.close()
