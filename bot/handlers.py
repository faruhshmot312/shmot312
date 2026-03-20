"""Обработчики команд Telegram-бота."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

from ai.engine import ask
from config import config
from sheets.registry import add_sheet, load_registry, remove_sheet

logger = logging.getLogger(__name__)
router = Router()


# --- Inline-кнопки ---

def main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню с кнопками."""
    buttons = [
        [
            InlineKeyboardButton(text="📊 Сводка", callback_data="report"),
            InlineKeyboardButton(text="📈 Воронка", callback_data="q:Покажи воронку продаж"),
        ],
        [
            InlineKeyboardButton(text="💰 Дебиторка", callback_data="q:Покажи дебиторку"),
            InlineKeyboardButton(text="🏭 Менеджеры ГШ", callback_data="q:Загрузка менеджеров из таблиц"),
        ],
        [
            InlineKeyboardButton(text="👥 Менеджеры", callback_data="q:Рейтинг менеджеров"),
            InlineKeyboardButton(text="⚠️ Просрочки", callback_data="q:Просроченные заказы"),
        ],
        [InlineKeyboardButton(text="📋 Еженедельный", callback_data="weekly")],
    ]
    # Кнопка дашборда если URL настроен
    if config.WEBAPP_URL:
        buttons.append([
            InlineKeyboardButton(
                text="📱 Дашборд",
                web_app=WebAppInfo(url=config.WEBAPP_URL),
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def safe_reply(message: Message, text: str, reply_markup=None) -> None:
    """Отправляет сообщение с Markdown, при ошибке — без форматирования."""
    chunks = [text[i:i + 4096] for i in range(0, len(text), 4096)]
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        try:
            await message.answer(chunk, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            try:
                await message.answer(chunk, reply_markup=markup)
            except Exception as e:
                logger.error("Не удалось отправить сообщение: %s", e)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    # Устанавливаем кнопку WebApp в меню бота
    if config.WEBAPP_URL:
        try:
            await message.bot.set_chat_menu_button(
                chat_id=message.chat.id,
                menu_button=MenuButtonWebApp(
                    text="📱 Дашборд",
                    web_app=WebAppInfo(url=config.WEBAPP_URL),
                ),
            )
        except Exception as e:
            logger.warning("Не удалось установить WebApp кнопку: %s", e)

    await safe_reply(
        message,
        "👋 Привет, Фарух!\n\n"
        "Я — твой бизнес-ассистент *Шмот312*.\n\n"
        "Нажми кнопку ниже или задай вопрос текстом:",
        reply_markup=main_keyboard(),
    )


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    if message.from_user:
        await safe_reply(message, f"Твой Chat ID: `{message.from_user.id}`")


@router.message(Command("sheets"))
async def cmd_sheets(message: Message) -> None:
    entries = load_registry()
    if not entries:
        await safe_reply(
            message,
            "📭 Нет подключённых таблиц.\n\n"
            "Добавь таблицу командой:\n"
            "`/add Название | ссылка_на_таблицу | описание`",
        )
        return

    lines = ["📋 *Подключённые таблицы:*\n"]
    for i, entry in enumerate(entries, 1):
        desc = f" — {entry.description}" if entry.description else ""
        lines.append(f"{i}. *{entry.name}*{desc}")
    await safe_reply(message, "\n".join(lines))


@router.message(Command("add"))
async def cmd_add(message: Message) -> None:
    if not message.text:
        return

    text = message.text.removeprefix("/add").strip()
    if not text or "|" not in text:
        await safe_reply(
            message,
            "Формат команды:\n"
            "`/add Название | ссылка_на_таблицу | описание`\n\n"
            "Пример:\n"
            "`/add ДДС | https://docs.google.com/spreadsheets/d/xxx | Движение денежных средств`",
        )
        return

    parts = [p.strip() for p in text.split("|")]
    name = parts[0]
    url = parts[1] if len(parts) > 1 else ""
    description = parts[2] if len(parts) > 2 else ""

    if not url.startswith("https://docs.google.com/spreadsheets"):
        await safe_reply(message, "❌ Ссылка должна быть на Google Sheets таблицу")
        return

    entry = add_sheet(name, url, description)
    await safe_reply(
        message,
        f"✅ Таблица *{entry.name}* добавлена!\n\n"
        "Данные появятся в кэше через 15 минут или после перезапуска бота.",
    )


@router.message(Command("remove"))
async def cmd_remove(message: Message) -> None:
    if not message.text:
        return

    text = message.text.removeprefix("/remove").strip()
    if not text:
        entries = load_registry()
        if not entries:
            await safe_reply(message, "Нет подключённых таблиц.")
            return
        lines = ["Укажи номер таблицы для удаления:\n"]
        for i, entry in enumerate(entries, 1):
            lines.append(f"{i}. {entry.name} — {entry.url}")
        lines.append("\nПример: `/remove 1`")
        await safe_reply(message, "\n".join(lines))
        return

    entries = load_registry()
    try:
        idx = int(text) - 1
        if 0 <= idx < len(entries):
            entry = entries[idx]
            remove_sheet(entry.url)
            await safe_reply(message, f"🗑 Таблица *{entry.name}* удалена.")
        else:
            await safe_reply(message, "❌ Неверный номер таблицы.")
    except ValueError:
        await safe_reply(message, "❌ Укажи номер таблицы (число).")


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    """Показывает главное меню с кнопками."""
    await safe_reply(message, "📌 *Главное меню:*", reply_markup=main_keyboard())


@router.message(Command("report"))
async def cmd_report(message: Message) -> None:
    """Генерирует утреннюю сводку по запросу."""
    thinking_msg = await message.answer("🔄 Генерирую сводку...")
    try:
        from ai.engine import generate_daily_report
        report = await generate_daily_report()
        await thinking_msg.delete()
        await safe_reply(message, report, reply_markup=main_keyboard())
    except Exception as e:
        await thinking_msg.delete()
        await safe_reply(message, f"❌ Ошибка: {e}")


@router.message(Command("weekly"))
async def cmd_weekly(message: Message) -> None:
    """Генерирует еженедельный отчёт по запросу."""
    thinking_msg = await message.answer("🔄 Генерирую еженедельный отчёт...")
    try:
        from ai.engine import generate_weekly_report
        report = await generate_weekly_report()
        await thinking_msg.delete()
        await safe_reply(message, report, reply_markup=main_keyboard())
    except Exception as e:
        await thinking_msg.delete()
        await safe_reply(message, f"❌ Ошибка: {e}")


# --- Callback queries (inline buttons) ---

@router.callback_query(F.data == "report")
async def cb_report(callback: CallbackQuery) -> None:
    await callback.answer()
    msg = await callback.message.answer("🔄 Генерирую сводку...")
    try:
        from ai.engine import generate_daily_report
        report = await generate_daily_report()
        await msg.delete()
        await safe_reply(callback.message, report, reply_markup=main_keyboard())
    except Exception as e:
        await msg.delete()
        await safe_reply(callback.message, f"❌ Ошибка: {e}")


@router.callback_query(F.data == "weekly")
async def cb_weekly(callback: CallbackQuery) -> None:
    await callback.answer()
    msg = await callback.message.answer("🔄 Генерирую еженедельный отчёт...")
    try:
        from ai.engine import generate_weekly_report
        report = await generate_weekly_report()
        await msg.delete()
        await safe_reply(callback.message, report, reply_markup=main_keyboard())
    except Exception as e:
        await msg.delete()
        await safe_reply(callback.message, f"❌ Ошибка: {e}")


@router.callback_query(F.data.startswith("q:"))
async def cb_question(callback: CallbackQuery) -> None:
    """Обработка вопросов из inline-кнопок."""
    await callback.answer()
    question = callback.data[2:]  # убираем "q:"
    msg = await callback.message.answer("🔄 Анализирую данные...")

    from cache.manager import is_cache_fresh
    if not await is_cache_fresh():
        await msg.edit_text("🔄 Обновляю данные...")
        from cache.manager import refresh_all
        await refresh_all()

    answer = await ask(question)
    await msg.delete()
    await safe_reply(callback.message, answer, reply_markup=main_keyboard())


@router.message(F.text)
async def handle_question(message: Message) -> None:
    """Обработка любого текстового сообщения как вопроса по данным."""
    from cache.manager import is_cache_fresh

    # Показываем typing
    await message.bot.send_chat_action(message.chat.id, "typing")
    thinking_msg = await message.answer("🔄 Анализирую данные...")

    # Проверяем кэш
    if not await is_cache_fresh():
        await thinking_msg.edit_text("🔄 Обновляю данные из таблиц и CRM...")
        from cache.manager import refresh_all
        await refresh_all()

    # Двухэтапный ИИ: маршрутизатор → аналитик
    answer = await ask(message.text)

    await thinking_msg.delete()
    await safe_reply(message, answer, reply_markup=main_keyboard())
