# tg-publisher-bot

Telegram-бот для автоматической публикации анонсов в канал. Принимает ссылку, извлекает содержимое, генерирует краткое описание через AI и публикует пост с хэштегами.

## Что умеет

- Обрабатывает **статьи**, **YouTube-видео**, **GitHub-репозитории** и **аудиофайлы**
- Генерирует анонс на русском языке через выбранный AI-провайдер
- Подбирает релевантные хэштеги из базы данных
- Поддерживает **очередь модерации** — посты требуют одобрения перед публикацией
- Управление пользователями и ролями (owner / admin)
- При отключённом AI публикует ссылку без анонса

## Как пользоваться

### Роли

Бот поддерживает два уровня доступа:

- **Owner** — задаётся через `OWNER_IDS` в `.env`. Может назначать и снимать администраторов, имеет все права администратора.
- **Admin** — назначается owner'ом. Может отправлять ссылки и управлять постами и хэштегами.

Пользователи без роли игнорируются ботом.

---

### Публикация поста

1. Отправьте боту ссылку в личные сообщения:
   ```
   https://habr.com/ru/articles/123456/
   https://www.youtube.com/watch?v=...
   https://github.com/owner/repo
   ```
2. Бот обработает ссылку и покажет предварительный просмотр поста.
3. Выберите действие:
   - **Опубликовать сейчас** — пост сразу уходит в канал
   - **На модерацию** — открывается расширенное меню с кнопками:
     - ✅ **Одобрить** — опубликовать как есть
     - ✏️ **Редактировать** — ввести новый текст поста, затем опубликовать
     - ❌ **Отклонить** — удалить пост из очереди

---

### Управление администраторами

> Только для owner'а

```
/add_admin 123456789       — назначить пользователя администратором
/remove_admin 123456789    — снять права администратора
```

Где `123456789` — Telegram ID пользователя (узнать можно через [@userinfobot](https://t.me/userinfobot)).

---

### Управление хэштегами

> Для owner и admin

```
/add_hashtag               — добавить хэштег (бот спросит тег и описание)
/list_hashtags             — показать все хэштеги с описаниями
/delete_hashtag #tools     — удалить хэштег
```

AI подбирает 1–3 хэштега из базы автоматически при обработке каждой ссылки. Чем точнее описания хэштегов — тем лучше подбор.

---

## Стек

- **Python 3.13** + [aiogram 3](https://docs.aiogram.dev/) (async Telegram bot)
- **PostgreSQL** + SQLAlchemy 2.0 (async ORM) + Alembic (миграции)
- **AI-провайдеры:** Claude, ChatGPT, Gemini, DeepSeek (переключаются через `.env`)
- **Транскрибация:** [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — локальная, без API-ключей
- **Docker** — multi-stage сборка (dev / prod)

## Структура проекта

```
src/
├── bot/            # Telegram-обработчики, FSM, middleware авторизации
├── services/       # Бизнес-логика: pipeline, пользователи, хэштеги
├── extractors/     # Парсинг контента: статьи, YouTube, GitHub, аудио
├── ai/             # AI-провайдеры, суммаризация, подбор хэштегов
├── publisher/      # Публикация в канал
├── db/             # Модели, сессия, репозиторий
└── config.py       # Настройки через Pydantic Settings
migrations/         # Alembic-миграции
tests/
├── unit/           # Юнит-тесты (с моками)
└── integration/    # Интеграционные тесты (реальная БД)
```

## Запуск локально

### 1. Требования

- Docker и Docker Compose

### 2. Настройка окружения

```bash
cp .env.example .env
```

Заполнить обязательные переменные в `.env`:

```env
BOT_TOKEN=           # токен от @BotFather
TELEGRAM_CHANNEL_ID= # ID канала, например -1001234567890
OWNER_IDS=           # ваш Telegram user ID

AI_PROVIDER=claude   # claude | chatgpt | gemini | deepseek
ANTHROPIC_API_KEY=   # ключ для выбранного провайдера

POSTGRES_DB=tgbot
POSTGRES_USER=tgbot
POSTGRES_PASSWORD=   # придумайте пароль
```

### 3. Запуск

```bash
make up       # поднять контейнеры (бот + PostgreSQL)
make migrate  # применить миграции БД
make logs     # смотреть логи
```

Бот готов к работе — отправьте ссылку в личные сообщения.

### 4. Остановка

```bash
make down
```

## AI-провайдеры

Выберите провайдер в `.env` и укажите соответствующий API-ключ:

| `AI_PROVIDER` | Переменная с ключом  | Где получить               |
|---------------|----------------------|----------------------------|
| `claude`      | `ANTHROPIC_API_KEY`  | console.anthropic.com      |
| `chatgpt`     | `OPENAI_API_KEY`     | platform.openai.com        |
| `gemini`      | `GEMINI_API_KEY`     | aistudio.google.com        |
| `deepseek`    | `DEEPSEEK_API_KEY`   | platform.deepseek.com      |
| *(пусто)*     | —                    | публикует только ссылку    |

> **Транскрибация аудио** использует локальный `faster-whisper` и не требует API-ключей. Настройте размер модели через `WHISPER_MODEL` в `.env` (по умолчанию `base`).

## Переменные окружения

| Переменная            | Обязательная | Описание                                          |
|-----------------------|:------------:|---------------------------------------------------|
| `BOT_TOKEN`           | ✅           | Токен бота от @BotFather                          |
| `TELEGRAM_CHANNEL_ID` | ✅           | ID канала для публикации                          |
| `OWNER_IDS`           | ✅           | Telegram ID владельцев через запятую              |
| `AI_PROVIDER`         |              | Провайдер AI (по умолчанию `claude`)              |
| `ANTHROPIC_API_KEY`   |              | Ключ Anthropic (если `AI_PROVIDER=claude`)        |
| `OPENAI_API_KEY`      |              | Ключ OpenAI (если `AI_PROVIDER=chatgpt`)          |
| `GEMINI_API_KEY`      |              | Ключ Google (если `AI_PROVIDER=gemini`)           |
| `DEEPSEEK_API_KEY`    |              | Ключ DeepSeek (если `AI_PROVIDER=deepseek`)       |
| `WHISPER_MODEL`       |              | Модель Whisper: `tiny`/`base`/`small`/`medium`/`large-v2` (по умолчанию `base`) |
| `WHISPER_DEVICE`      |              | Устройство: `cpu` или `cuda` (по умолчанию `cpu`) |
| `POSTGRES_DB`         | ✅           | Имя базы данных                                   |
| `POSTGRES_USER`       | ✅           | Пользователь PostgreSQL                           |
| `POSTGRES_PASSWORD`   | ✅           | Пароль PostgreSQL                                 |
| `GITHUB_TOKEN`        |              | Токен GitHub (для увеличения лимитов API)         |
| `ENV`                 |              | `dev` или `prod` (влияет на сборку Docker)        |
| `RESTART_POLICY`      |              | `unless-stopped` (dev) / `always` (prod)          |
| `LOG_LEVEL`           |              | `DEBUG` (dev) / `INFO` (prod)                     |

## Команды Make

```bash
make up       # запустить бота и PostgreSQL
make down     # остановить контейнеры
make logs     # логи бота в реальном времени
make shell    # bash внутри контейнера бота
make migrate  # применить миграции Alembic
make lint     # проверка кода через ruff
make test     # запустить тесты
make build    # собрать production Docker-образ
```

## Тесты

```bash
make test
```

Юнит-тесты работают без Docker. Интеграционные тесты требуют запущенного PostgreSQL (`make up`).

## Деплой на production

В `.env` на сервере установить:

```env
ENV=prod
RESTART_POLICY=always
LOG_LEVEL=INFO
POSTGRES_PASSWORD=  # надёжный пароль
```

Затем:

```bash
make up
make migrate
```

## Лицензия

[MIT](LICENSE)
