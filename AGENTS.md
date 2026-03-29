# AGENTS.md

> Project map for AI agents. Keep this file up-to-date as the project evolves.

## Project Overview
A Telegram bot that automatically creates and publishes posts to a Telegram channel by analyzing input content (articles, YouTube videos, GitHub repositories, etc.) and generating concise 2-3 sentence announcements using Claude AI. Supports optional moderation before publishing.

## Tech Stack
- **Language:** Python 3.13
- **Framework:** aiogram 3 (async Telegram bot framework)
- **Database:** PostgreSQL with SQLAlchemy (async) + Alembic
- **AI:** Claude API (claude-sonnet-4-6) via Anthropic SDK
- **Content Extraction:** httpx + BeautifulSoup4, youtube-transcript-api, GitHub REST API

## Project Structure
```
tg-publisher-bot/
├── src/                        # Application source code
│   ├── __main__.py             # Entry point (python -m src)
│   ├── config.py               # Pydantic Settings — all env vars
│   ├── bot/                    # aiogram bot handlers, FSM states, keyboards
│   │   ├── main.py             # Bot + Dispatcher setup, startup/shutdown
│   │   ├── states.py           # FSM state groups
│   │   ├── keyboards.py        # Inline keyboard builders
│   │   ├── handlers/
│   │   │   ├── url_input.py    # URL handling + moderation callbacks
│   │   │   ├── edit_post.py    # FSM post editing handler
│   │   │   ├── roles.py        # /add_admin, /remove_admin
│   │   │   └── hashtags.py     # /add_hashtag, /list_hashtags, /delete_hashtag
│   │   └── middlewares/
│   │       └── auth.py         # Role auth OuterMiddleware
│   ├── services/               # Business logic orchestration
│   │   ├── pipeline.py         # Full URL → extract → AI → publish pipeline
│   │   ├── users.py            # User role management
│   │   └── hashtags.py         # Hashtag service
│   ├── extractors/             # Content extraction (one module per source type)
│   │   ├── base.py             # ExtractedContent dataclass + BaseExtractor + registry
│   │   ├── detector.py         # ContentType enum + detect_content_type(url)
│   │   ├── article.py          # Web article (httpx + BeautifulSoup4)
│   │   ├── youtube.py          # YouTube (transcript-api + yt-dlp + Whisper fallback)
│   │   ├── github.py           # GitHub REST API (README + metadata)
│   │   └── audio.py            # Direct audio URL → OpenAI Whisper
│   ├── ai/                     # AI layer
│   │   ├── summarizer.py       # Claude: 2-3 sentence Russian announcement
│   │   ├── hashtag_matcher.py  # Claude: pick 1-3 hashtags from DB list
│   │   └── composer.py         # Assemble final post text
│   ├── publisher/              # Channel publishing
│   │   └── channel.py          # Send HTML post to TELEGRAM_CHANNEL_ID
│   └── db/                     # Database layer
│       ├── models.py           # SQLAlchemy ORM models (User, Post, Hashtag, PostHashtag)
│       ├── session.py          # Async engine + sessionmaker + get_session()
│       └── repository.py       # All DB access functions (CRUD + deduplication)
├── migrations/                 # Alembic migration scripts
│   ├── env.py                  # Async Alembic env
│   └── versions/
│       └── 0001_initial.py     # Initial schema migration
├── tests/
│   ├── unit/
│   │   ├── test_detector.py
│   │   ├── test_extractors.py
│   │   ├── test_summarizer.py
│   │   └── test_pipeline.py
│   └── integration/
│       ├── conftest.py         # PostgreSQL test session fixtures
│       └── test_repository.py
├── .github/workflows/
│   ├── ci.yml                  # Lint + unit + integration tests
│   └── cd.yml                  # Build → push to ghcr.io → SSH deploy
├── Dockerfile                  # Multi-stage: dev + prod (includes ffmpeg)
├── docker-compose.yml          # Dev: bot + postgres
├── docker-compose.production.yml
├── Makefile                    # up/down/logs/migrate/lint/test/build targets
├── alembic.ini
├── .env.example
└── pyproject.toml
```

## Key Entry Points
| File | Purpose |
|------|---------|
| `src/__main__.py` | Entry point — `python -m src` starts polling |
| `src/bot/main.py` | Bot + Dispatcher setup, router registration |
| `src/services/pipeline.py` | Full processing pipeline orchestration |
| `src/config.py` | Loads env vars (BOT_TOKEN, ANTHROPIC_API_KEY, DATABASE_URL, etc.) |
| `migrations/versions/0001_initial.py` | Initial DB schema |
| `pyproject.toml` | Dependencies and project metadata |

## Documentation
| Document | Path | Description |
|----------|------|-------------|
| README | README.md | Project landing page |

## AI Context Files
| File | Purpose |
|------|---------|
| AGENTS.md | This file — project structure map |
| .ai-factory/DESCRIPTION.md | Project specification and tech stack |
| .ai-factory/ARCHITECTURE.md | Architecture decisions and guidelines |
