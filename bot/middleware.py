"""Middleware авторизации — только Фарух может пользоваться ботом."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from config import config


class AuthMiddleware(BaseMiddleware):
    """Пропускает сообщения только от ADMIN_CHAT_ID."""

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        if config.ADMIN_CHAT_ID == 0:
            return await handler(event, data)

        user = event.from_user
        if user and user.id == config.ADMIN_CHAT_ID:
            return await handler(event, data)

        # Для неавторизованных
        if isinstance(event, Message) and user:
            await event.answer(
                f"⛔ Доступ запрещён.\n\nТвой Chat ID: `{user.id}`\n"
                "Передай его владельцу бота для добавления доступа.",
                parse_mode="Markdown",
            )
        elif isinstance(event, CallbackQuery):
            await event.answer("⛔ Доступ запрещён", show_alert=True)

        return None
