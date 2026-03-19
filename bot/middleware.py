"""Middleware авторизации — только Фарух может пользоваться ботом."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

from config import config


class AuthMiddleware(BaseMiddleware):
    """Пропускает сообщения только от ADMIN_CHAT_ID."""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if config.ADMIN_CHAT_ID == 0:
            # Если ADMIN_CHAT_ID не задан — пропускаем всех (для первоначальной настройки)
            return await handler(event, data)

        if event.from_user and event.from_user.id == config.ADMIN_CHAT_ID:
            return await handler(event, data)

        # Для неавторизованных — показываем их chat_id (полезно при настройке)
        if event.from_user:
            await event.answer(
                f"⛔ Доступ запрещён.\n\nТвой Chat ID: `{event.from_user.id}`\n"
                "Передай его владельцу бота для добавления доступа.",
                parse_mode="Markdown",
            )
        return None
