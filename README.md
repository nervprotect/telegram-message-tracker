# Деплой бота на Railway

Папка самодостаточная: `bot.py`, `Dockerfile`, `requirements.txt`, `railway.toml`.
Токен в код **не зашит** — берётся из переменной окружения `BOT_TOKEN`.

## Шаги

### 1. Залей папку в GitHub
Создай **приватный** репозиторий и закоммить содержимое этой папки (`deploy/`).
`.gitignore` уже исключает `state.json`, `.env` и сессии.

> Если репозиторий публичный — токен всё равно в безопасности, его нет в файлах.

### 2. Создай проект на Railway
1. https://railway.app → **New Project** → **Deploy from GitHub repo**
2. Выбери репозиторий. Если файлы лежат в подпапке `deploy/` —
   Settings → **Root Directory** → укажи `deploy`
3. Railway увидит `Dockerfile` и соберёт образ сам

### 3. Переменные окружения
Service → **Variables** → добавь:

| Переменная | Значение |
|------------|----------|
| `BOT_TOKEN` | токен от @BotFather |
| `ADMIN_ID` | `347799240` |
| `DATA_DIR` | `/data` |

### 4. Volume для сохранения состояния (важно!)
Файловая система Railway эфемерна — без Volume бот забудет подключения и настройки при каждом рестарте.

1. Service → **Settings** → **Volumes** → **New Volume**
2. Mount path: **`/data`**
3. Убедись, что переменная `DATA_DIR=/data` задана (шаг 3)

Теперь `state.json` хранится на Volume и переживает перезапуски.

### 5. Deploy
Railway задеплоит автоматически. В логах должно появиться:
```
Bot started, polling...
Application started
```

## ⚠️ Важные правила

- **Только один экземпляр.** Telegram разрешает один `getUpdates` на токен.
  Не ставь `numReplicas > 1` и **выключи локальный bot.py**, пока бот крутится на Railway
  (иначе конфликт `409 Conflict`).
- **Business Mode** у бота должен быть включён в @BotFather
  (Bot Settings → Business Mode → ON).
- После деплоя подключи бота в Telegram → Настройки → Telegram Business → Чат-боты.

## Деплой на Render (альтернатива Railway)

В папке уже есть `render.yaml` — Render подхватит его автоматически при создании сервиса
из этого репозитория (New → Blueprint, или New → Web Service → он найдёт `render.yaml`).

Render free-план **не даёт постоянных дисков** (в отличие от Railway Volume), поэтому вместо
`DATA_DIR=/data` используется Redis:

1. Заведи бесплатный Redis, например на [Upstash](https://upstash.com) (без ограничения по времени,
   в отличие от бесплатного Postgres на самом Render).
2. Service → **Environment** → добавь:

   | Переменная | Значение |
   |------------|----------|
   | `BOT_TOKEN` | токен от @BotFather |
   | `ADMIN_ID` | `347799240` |
   | `REDIS_URL` | строка подключения вида `rediss://default:...@...upstash.io:6379` |

   Без `REDIS_URL` бот работает как раньше — пишет `state.json` локально, и это
   теряется при каждом рестарте/редеплое (Render free-план засыпает через ~15 минут простоя).
3. Бот по-прежнему работает через long polling — `render.yaml` просто заодно поднимает
   HTTP-порт для health-check'а Render, это не влияет на получение сообщений.

## Локальный запуск этой папки (по желанию)
```bash
set BOT_TOKEN=твой_токен        # PowerShell: $env:BOT_TOKEN="..."
set ADMIN_ID=347799240
pip install -r requirements.txt
python bot.py
```
