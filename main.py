"""Точка входа — запуск Telegram-бота Шмот312."""

import asyncio
import base64
import logging
import os
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

# Декодируем credentials из env (для Railway)
creds_b64 = os.environ.get("GOOGLE_CREDENTIALS_B64")
if creds_b64:
    creds_path = Path(__file__).parent / "credentials.json"
    if not creds_path.exists():
        creds_path.write_bytes(base64.b64decode(creds_b64))

from bot.main import start_bot  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Приглушаем логи библиотек
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiogram").setLevel(logging.WARNING)


def main() -> None:
    print("🚀 Запуск бота Шмот312...")
    print("Для остановки нажми Ctrl+C")
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен.")


if __name__ == "__main__":
    main()
