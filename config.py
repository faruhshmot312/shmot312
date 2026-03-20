import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv(Path(__file__).parent / ".env")


class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    ADMIN_CHAT_ID: int = int(os.environ.get("ADMIN_CHAT_ID", "0"))

    # Claude API
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    AI_MODEL: str = "claude-sonnet-4-20250514"
    AI_ROUTER_MODEL: str = "claude-haiku-4-5-20251001"

    # Google Sheets
    GOOGLE_CREDENTIALS_FILE: str = os.environ.get(
        "GOOGLE_CREDENTIALS_FILE",
        str(Path(__file__).parent / "credentials.json"),
    )

    # Bitrix24
    BITRIX24_WEBHOOK_URL: str = os.environ.get("BITRIX24_WEBHOOK_URL", "")

    # Cache
    DB_PATH: str = str(Path(__file__).parent / "cache.db")
    CACHE_TTL_MINUTES: int = 15

    # Scheduler — время утренней сводки (часы, минуты, таймзона)
    DAILY_REPORT_HOUR: int = 9
    DAILY_REPORT_MINUTE: int = 0
    TIMEZONE: str = "Asia/Bishkek"

    # Алерты — пороговые значения (в сомах)
    ALERT_CASH_MIN: float = 50_000
    ALERT_DEBT_MAX: float = 50_000
    ALERT_EXPENSE_MAX: float = 100_000
    ALERT_ORDERS_MIN: int = 3

    # WebApp
    WEBAPP_HOST: str = "0.0.0.0"
    WEBAPP_PORT: int = 8080
    WEBAPP_URL: str = os.environ.get("WEBAPP_URL", "")  # https://your-domain.com


config = Config()
