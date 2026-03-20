# Деплой Шмот312 бота на Railway

## Что нужно
- Аккаунт на [railway.app](https://railway.app) (вход через GitHub)
- GitHub репозиторий (уже есть: faruhshmot312/shmot312)

## Шаги

### 1. Зайди на Railway
1. Открой https://railway.app
2. Войди через GitHub аккаунт

### 2. Создай проект
1. Нажми **"New Project"**
2. Выбери **"Deploy from GitHub Repo"**
3. Найди репозиторий **shmot312** и выбери его
4. Railway автоматически обнаружит Dockerfile и начнёт деплой

### 3. Настрой переменные окружения
В настройках проекта (вкладка **Variables**) добавь:

| Переменная | Значение |
|---|---|
| `TELEGRAM_BOT_TOKEN` | токен бота из @BotFather |
| `ADMIN_CHAT_ID` | твой Telegram ID |
| `ANTHROPIC_API_KEY` | ключ API Claude |
| `BITRIX24_WEBHOOK_URL` | вебхук Bitrix24 |
| `GOOGLE_CREDENTIALS_FILE` | `/app/credentials.json` |

### 4. Получи URL для WebApp
1. После деплоя Railway даст публичный URL (типа `https://shmot312-xxx.up.railway.app`)
2. Скопируй этот URL
3. Добавь в переменные окружения: `WEBAPP_URL` = скопированный URL
4. Railway автоматически передеплоит

### 5. Проверь
1. Открой бота в Telegram
2. Нажми `/start`
3. Должна появиться кнопка **"Дашборд"**
4. Нажми — откроется мини-приложение с аналитикой

### 6. Google Credentials
Файл `credentials.json` должен быть в репозитории (уже добавлен).
Если нужно обновить — замени файл и запуш в GitHub.

## Полезные команды

```bash
# Посмотреть логи
railway logs

# Передеплой
git push origin main
```

## Стоимость
Railway бесплатный тариф: $5/мес кредитов, хватает для бота.
Hobby план: $5/мес — без лимитов.
