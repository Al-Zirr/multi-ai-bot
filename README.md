# Multi-AI Telegram Bot

**[English](#english) | [Русский](#русский)**

---

<a id="english"></a>

## English

Personal Telegram bot that combines **GPT**, **Claude**, and **Gemini** in one interface with streaming responses, voice synthesis, image generation, web search, RAG, translation, YouTube tools, and more.

> Built for personal use. One bot — all AI models, switchable on the fly.

---

### Features

#### Core AI
| Feature | Description |
|---------|-------------|
| **3 AI Models** | GPT-5.2, Claude Opus 4.6, Gemini 3 Pro — switch instantly |
| **Streaming** | Real-time token-by-token output with cursor animation |
| **"Ask All"** | Send one message to all 3 models, get 3 responses side by side |
| **Smart Context** | 20-message sliding window + automatic summarization of older context |
| **Memory** | Bot remembers facts about you (name, preferences) across sessions |
| **Model Persistence** | Selected model saved per user in database |

#### Search & RAG
| Feature | Description |
|---------|-------------|
| **Web Search** | Tavily-powered search with auto-detection of search queries |
| **RAG** | Upload PDF/DOCX/XLSX/TXT/images — bot extracts text, chunks, embeds with pgvector, retrieves relevant context |
| **Image OCR** | Extract text from photos (PyMuPDF, python-docx, openpyxl) |

#### Voice
| Feature | Description |
|---------|-------------|
| **Voice Input** | Whisper STT — send voice message, get text + AI response |
| **TTS** | OpenAI TTS (gpt-4o-mini-tts) with per-model voices (ash/onyx/echo) |
| **TTS Pipeline** | Text normalization, yofikation, stress placement (russtress), custom pronunciation dictionary |

#### Translation (RU / AR)
| Feature | Description |
|---------|-------------|
| **Bidirectional** | Russian to Arabic / Arabic to Russian |
| **Input modes** | Text, voice messages, photos (OCR), documents |
| **3-Model Compare** | Translate with one model, then instantly compare all 3 |
| **Custom prompts** | Specialized prompts for Islamic terminology (Aqeedah, Fiqh) |
| **Glossary** | Per-user glossary with pgvector similarity search |
| **Translation Memory** | Stores previous translations, finds similar segments |

#### Image Generation
| Feature | Description |
|---------|-------------|
| **DALL-E 3** | With size/style/quality controls |
| **Gemini Imagen 3** | Google's image model |
| **Flux 2 Pro** | Black Forest Labs model |
| **Inline controls** | Switch provider, size, style, regenerate — all via buttons |

#### YouTube
| Feature | Description |
|---------|-------------|
| **Video info** | Send YouTube link — get title, channel, duration |
| **AI Summary** | Full transcript extraction + AI summarization |
| **Download video** | Choose quality (360p-1080p), progress bar |
| **Download audio** | MP3 128/320 kbps or WAV, FFmpeg conversion with progress |

#### Utilities
| Feature | Description |
|---------|-------------|
| **Bookmarks** | Save any AI response, add notes, search, paginated list |
| **Export** | Export full dialog as Markdown, JSON, or PDF |
| **Telegraph** | Long responses (>3800 chars) auto-published to Telegraph |
| **Balance tracker** | Per-service spending tracking with token-level pricing |
| **Debate mode** | Two AI models debate a topic you choose |

---

### Architecture

```
Telegram  <-->  aiogram 3.x Dispatcher
                    |
          +---------+---------+
          |         |         |
       Handlers  Keyboards  Middlewares
          |                    |
       Services              Auth
          |
    +-----+-----+-----+-----+
    |     |     |     |     |
  OpenAI  Anthropic  Gemini  ...
    |     |     |     |
    +-----+-----+-----+
          |
    PostgreSQL + pgvector
```

**Key design decisions:**
- `network_mode: host` — bot runs on host network to access XRay proxy on `127.0.0.1:10809`
- Dual-outbound proxy: Latvia (default) + USA (for Google AI API which blocks RU IPs)
- All services injected into aiogram Dispatcher as dependencies
- Async-first: asyncpg, httpx, aiohttp throughout
- Streaming via periodic `message.edit_text()` with 1-second throttle

---

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Bot framework | aiogram 3.x |
| Language | Python 3.12 |
| Database | PostgreSQL 16 + pgvector |
| ORM | SQLAlchemy 2.x (async) |
| Migrations | Alembic |
| AI: GPT | OpenAI SDK (`openai`) |
| AI: Claude | Anthropic SDK (`anthropic`) |
| AI: Gemini | Google GenAI SDK (`google-genai`) |
| Search | Tavily API |
| Embeddings | OpenAI text-embedding-3-small |
| TTS/STT | OpenAI Whisper + TTS |
| Stress marks | russtress + TensorFlow/Keras |
| Image gen | DALL-E 3, Gemini Imagen, Flux 2 Pro |
| YouTube | yt-dlp + youtube-transcript-api |
| PDF/Documents | PyMuPDF, python-docx, openpyxl |
| Long text | Telegraph API |
| Container | Docker + Docker Compose |
| Proxy | XRay/VLESS (dual outbound) |

---

### Project Structure

```
multi-ai-bot/
├── bot/
│   ├── main.py                 # Entry point, dispatcher setup
│   ├── config.py               # Configuration from .env
│   ├── database.py             # SQLAlchemy async engine
│   │
│   ├── handlers/               # Telegram message/callback handlers
│   │   ├── chat.py             # Main chat (text messages → AI)
│   │   ├── start.py            # /start, /help, /clear, /balance, etc.
│   │   ├── model_switch.py     # /model — switch AI provider
│   │   ├── translator.py       # Translation mode (RU↔AR)
│   │   ├── voice.py            # Voice messages (STT + TTS)
│   │   ├── imagegen.py         # /imagine — image generation
│   │   ├── youtube.py          # YouTube links — summary/download
│   │   ├── bookmarks.py        # /bookmarks, /export
│   │   ├── files.py            # Document upload (RAG)
│   │   ├── images.py           # Photo OCR
│   │   ├── search.py           # /search
│   │   ├── memory.py           # /memory — user facts
│   │   ├── debate.py           # AI debate mode
│   │   └── settings.py         # /settings — user preferences
│   │
│   ├── keyboards/              # Inline/reply keyboard builders
│   │   ├── main_menu.py        # Reply keyboard (bottom menu)
│   │   ├── model_select.py     # Model switch + response buttons
│   │   ├── imagegen.py         # Image gen controls
│   │   ├── translator.py       # Translator mode keyboard
│   │   ├── youtube.py          # YouTube action keyboards
│   │   └── settings.py         # Settings keyboard
│   │
│   ├── middlewares/
│   │   └── auth.py             # Whitelist by ADMIN_IDS
│   │
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── conversation.py     # Chat history
│   │   ├── context_summary.py  # Summarized context
│   │   ├── user_settings.py    # Per-user preferences
│   │   ├── bookmark.py         # Saved responses
│   │   ├── memory.py           # User facts
│   │   ├── embedding.py        # RAG document embeddings
│   │   ├── file.py             # Uploaded files metadata
│   │   ├── translator.py       # Glossary + translation memory
│   │   ├── service_balance.py  # API spending tracker
│   │   ├── pronunciation_rule.py
│   │   └── stress_override.py
│   │
│   ├── services/               # Business logic
│   │   ├── ai_router.py        # Route to GPT/Claude/Gemini
│   │   ├── openai_service.py   # OpenAI chat completions
│   │   ├── anthropic_service.py # Claude messages API
│   │   ├── gemini_service.py   # Gemini generate_content
│   │   ├── streaming_service.py # Real-time streaming to Telegram
│   │   ├── context_service.py  # Context window + summarization
│   │   ├── memory_service.py   # Fact extraction + storage
│   │   ├── search_service.py   # Tavily web search
│   │   ├── rag_service.py      # Embeddings + vector search
│   │   ├── translator_service.py # Translation logic
│   │   ├── voice_service.py    # TTS + STT
│   │   ├── tts_pipeline.py     # Text normalization for TTS
│   │   ├── image_service.py    # DALL-E / Imagen / Flux
│   │   ├── youtube_service.py  # yt-dlp + transcripts
│   │   ├── bookmark_service.py # Bookmarks CRUD
│   │   ├── export_service.py   # Dialog export (MD/JSON/PDF)
│   │   ├── balance_service.py  # Spending tracker
│   │   ├── settings_service.py # User settings CRUD
│   │   ├── telegraph_service.py # Long text → Telegraph
│   │   ├── file_service.py     # File storage
│   │   └── debate_service.py   # AI debate orchestration
│   │
│   ├── utils/
│   │   ├── formatting.py       # Markdown → Telegram HTML converter
│   │   └── prompts.py          # Centralized system prompts
│   │
│   └── data/
│       └── yo.dat              # Yofikation dictionary
│
├── alembic/                    # Database migrations
├── prompts/                    # External prompt files
│   ├── akida.txt               # Islamic Aqeedah translation prompt
│   └── fiqh.txt                # Islamic Fiqh translation prompt
├── scripts/
│   └── backup_db.sh            # Daily PostgreSQL backup
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

---

### Installation

#### Prerequisites

- Docker + Docker Compose
- API keys: OpenAI, Anthropic, Google AI
- Telegram bot token from [@BotFather](https://t.me/BotFather)
- (Optional) Tavily API key, BFL API key
- (Optional) SOCKS5/HTTP proxy for restricted regions

#### Setup

```bash
# Clone
git clone https://github.com/YOUR_USER/multi-ai-bot.git
cd multi-ai-bot

# Configure
cp .env.example .env
nano .env  # Fill in your API keys

# Launch
docker compose up -d

# Check logs
docker logs -f multi_ai_bot
```

#### Proxy (for restricted regions)

If your server's IP is blocked by Google AI or other providers, set up a proxy (e.g., XRay/VLESS) and add to `.env` or `docker-compose.yml`:

```yaml
environment:
  HTTP_PROXY: http://127.0.0.1:10809
  HTTPS_PROXY: http://127.0.0.1:10809
```

The bot uses `network_mode: host` to share the host's network stack, including any localhost proxies.

---

### Services

#### AI Router (`ai_router.py`)
Routes user messages to the selected AI provider. Supports per-user model selection (saved in DB) and "Ask All" mode.

#### Streaming (`streaming_service.py`)
Sends AI responses token-by-token with a cursor (`▌`), updating the Telegram message every 1 second. Falls back to plain text if HTML parsing fails. Auto-publishes to Telegraph for responses >3800 characters.

#### Context (`context_service.py`)
Maintains a 20-message sliding window. When exceeded, older messages are summarized by AI and stored as a single system message, preserving conversation coherence while saving tokens.

#### Memory (`memory_service.py`)
Automatically extracts facts about the user from conversations (name, preferences, interests). Facts are categorized and always included in the system prompt.

#### Translator (`translator_service.py`)
Bidirectional RU↔AR translation with specialized prompts, per-user glossary (stored as pgvector embeddings for fuzzy matching), and translation memory.

#### Voice (`voice_service.py` + `tts_pipeline.py`)
STT via OpenAI Whisper. TTS via OpenAI gpt-4o-mini-tts with a full normalization pipeline: number expansion, yofikation, stress placement (russtress + custom overrides), pronunciation dictionary.

#### YouTube (`youtube_service.py`)
Powered by yt-dlp with cookie authentication and Node.js EJS challenge solver. Extracts video info, transcripts (youtube-transcript-api), downloads video/audio with real-time progress bars.

#### Balance (`balance_service.py`)
Tracks spending per API service based on token usage with per-model pricing.

---

### API Costs (per 1M tokens)

| Model | Input | Output |
|-------|-------|--------|
| GPT-5.2 | $1.75 | $14.00 |
| Claude Opus 4.6 | $15.00 | $75.00 |
| Gemini 3 Pro | $1.25 | $10.00 |

| Service | Price |
|---------|-------|
| Whisper STT | $0.006/min |
| TTS (gpt-4o-mini-tts) | $0.60/1M chars |
| DALL-E 3 (1024x1024) | $0.040/image |
| DALL-E 3 HD | $0.080/image |
| Gemini Imagen 3 | $0.040/image |
| Flux 2 Pro | $0.050/image |
| Embeddings (text-embedding-3-small) | $0.020/1M tokens |
| Tavily Search | Free tier: 1000 req/mo |

---

### Bot Commands

| Command | Description |
|---------|-------------|
| `/model` | Switch AI model (GPT / Claude / Gemini / All) |
| `/search` | Web search via Tavily |
| `/imagine` | Generate images (DALL-E 3 / Imagen / Flux) |
| `/memory` | View/manage stored facts about you |
| `/bookmarks` | View saved AI responses |
| `/export` | Export dialog (Markdown / JSON / PDF) |
| `/balance` | Check API spending |
| `/pronounce` | Manage TTS pronunciation dictionary |
| `/fix` | Manage stress mark overrides |
| `/glossary` | Manage translator glossary |
| `/translator_prompt` | Manage translator prompts |
| `/context` | View context window stats |
| `/clear` | Clear conversation history |
| `/help` | Show all commands |

**Inline buttons under responses:** Regenerate, Ask another model, TTS, Save bookmark.

**Menu buttons:** Модель, Переводчик, Генерация, Баланс, Контекст, Очистить.

---

### Backups

Automatic daily PostgreSQL backups via cron (3:00 AM):

```bash
# Manual backup
./scripts/backup_db.sh

# Backups stored in /media/hdd/ai-bot/backups/
# Retention: 7 days
```

---

### Roadmap

- [ ] Auto-install script for one-click deployment
- [ ] Web dashboard for settings and analytics
- [ ] Multi-user support with separate quotas
- [ ] Scheduled messages / reminders
- [ ] Plugin system for custom handlers
- [ ] Local Bot API server for large file uploads

---

### License

MIT License. See [LICENSE](LICENSE) for details.

---

<a id="русский"></a>

## Русский

Персональный Telegram-бот, объединяющий **GPT**, **Claude** и **Gemini** в одном интерфейсе со стримингом ответов, голосовым синтезом, генерацией изображений, веб-поиском, RAG, переводом, инструментами YouTube и многим другим.

> Создан для личного использования. Один бот — все AI-модели, переключение на лету.

---

### Возможности

#### Основной AI
| Функция | Описание |
|---------|----------|
| **3 AI-модели** | GPT-5.2, Claude Opus 4.6, Gemini 3 Pro — мгновенное переключение |
| **Стриминг** | Вывод ответа токен за токеном в реальном времени с анимацией курсора |
| **"Спросить всех"** | Отправить одно сообщение всем 3 моделям, получить 3 ответа рядом |
| **Умный контекст** | Скользящее окно в 20 сообщений + автоматическая суммаризация старого контекста |
| **Память** | Бот запоминает факты о вас (имя, предпочтения) между сессиями |
| **Сохранение модели** | Выбранная модель сохраняется для каждого пользователя в базе данных |

#### Поиск и RAG
| Функция | Описание |
|---------|----------|
| **Веб-поиск** | Поиск через Tavily с автоопределением поисковых запросов |
| **RAG** | Загрузка PDF/DOCX/XLSX/TXT/изображений — бот извлекает текст, разбивает на чанки, создаёт эмбеддинги через pgvector, находит релевантный контекст |
| **OCR изображений** | Извлечение текста из фотографий (PyMuPDF, python-docx, openpyxl) |

#### Голос
| Функция | Описание |
|---------|----------|
| **Голосовой ввод** | Whisper STT — отправьте голосовое сообщение, получите текст + ответ AI |
| **TTS** | OpenAI TTS (gpt-4o-mini-tts) с отдельными голосами для каждой модели (ash/onyx/echo) |
| **TTS-пайплайн** | Нормализация текста, ёфикация, расстановка ударений (russtress), пользовательский словарь произношений |

#### Перевод (RU / AR)
| Функция | Описание |
|---------|----------|
| **Двунаправленный** | Русский на арабский / арабский на русский |
| **Режимы ввода** | Текст, голосовые сообщения, фото (OCR), документы |
| **Сравнение 3 моделей** | Перевести одной моделью, затем мгновенно сравнить все 3 |
| **Кастомные промпты** | Специализированные промпты для исламской терминологии (Акыда, Фикх) |
| **Глоссарий** | Пользовательский глоссарий с поиском по схожести через pgvector |
| **Память переводов** | Хранит предыдущие переводы, находит похожие сегменты |

#### Генерация изображений
| Функция | Описание |
|---------|----------|
| **DALL-E 3** | С настройками размера, стиля и качества |
| **Gemini Imagen 3** | Модель генерации изображений Google |
| **Flux 2 Pro** | Модель Black Forest Labs |
| **Inline-управление** | Переключение провайдера, размера, стиля, перегенерация — всё через кнопки |

#### YouTube
| Функция | Описание |
|---------|----------|
| **Информация о видео** | Отправьте ссылку YouTube — получите название, канал, длительность |
| **AI-выжимка** | Полное извлечение субтитров + суммаризация через AI |
| **Скачивание видео** | Выбор качества (360p-1080p), прогресс-бар |
| **Скачивание аудио** | MP3 128/320 kbps или WAV, конвертация FFmpeg с прогрессом |

#### Утилиты
| Функция | Описание |
|---------|----------|
| **Закладки** | Сохранение любого ответа AI, добавление заметок, поиск, пагинация |
| **Экспорт** | Экспорт полного диалога в Markdown, JSON или PDF |
| **Telegraph** | Длинные ответы (>3800 символов) автоматически публикуются в Telegraph |
| **Трекер расходов** | Отслеживание трат по сервисам с точностью до токенов |
| **Режим дебатов** | Две AI-модели дебатируют на выбранную тему |

---

### Архитектура

```
Telegram  <-->  aiogram 3.x Dispatcher
                    |
          +---------+---------+
          |         |         |
       Handlers  Keyboards  Middlewares
          |                    |
       Services              Auth
          |
    +-----+-----+-----+-----+
    |     |     |     |     |
  OpenAI  Anthropic  Gemini  ...
    |     |     |     |
    +-----+-----+-----+
          |
    PostgreSQL + pgvector
```

**Ключевые архитектурные решения:**
- `network_mode: host` — бот работает в сети хоста для доступа к XRay-прокси на `127.0.0.1:10809`
- Двойной исходящий прокси: Латвия (по умолчанию) + США (для Google AI API, который блокирует российские IP)
- Все сервисы внедряются в Dispatcher aiogram как зависимости
- Async-first: asyncpg, httpx, aiohttp повсюду
- Стриминг через периодический `message.edit_text()` с интервалом в 1 секунду

---

### Стек технологий

| Компонент | Технология |
|-----------|-----------|
| Фреймворк бота | aiogram 3.x |
| Язык | Python 3.12 |
| База данных | PostgreSQL 16 + pgvector |
| ORM | SQLAlchemy 2.x (async) |
| Миграции | Alembic |
| AI: GPT | OpenAI SDK (`openai`) |
| AI: Claude | Anthropic SDK (`anthropic`) |
| AI: Gemini | Google GenAI SDK (`google-genai`) |
| Поиск | Tavily API |
| Эмбеддинги | OpenAI text-embedding-3-small |
| TTS/STT | OpenAI Whisper + TTS |
| Ударения | russtress + TensorFlow/Keras |
| Генерация изображений | DALL-E 3, Gemini Imagen, Flux 2 Pro |
| YouTube | yt-dlp + youtube-transcript-api |
| PDF/Документы | PyMuPDF, python-docx, openpyxl |
| Длинные тексты | Telegraph API |
| Контейнеры | Docker + Docker Compose |
| Прокси | XRay/VLESS (двойной outbound) |

---

### Структура проекта

```
multi-ai-bot/
├── bot/
│   ├── main.py                 # Точка входа, настройка dispatcher
│   ├── config.py               # Конфигурация из .env
│   ├── database.py             # Async-движок SQLAlchemy
│   │
│   ├── handlers/               # Обработчики сообщений/callback
│   │   ├── chat.py             # Основной чат (текст → AI)
│   │   ├── start.py            # /start, /help, /clear, /balance и др.
│   │   ├── model_switch.py     # /model — переключение AI-провайдера
│   │   ├── translator.py       # Режим перевода (RU↔AR)
│   │   ├── voice.py            # Голосовые сообщения (STT + TTS)
│   │   ├── imagegen.py         # /imagine — генерация изображений
│   │   ├── youtube.py          # YouTube ссылки — выжимка/скачивание
│   │   ├── bookmarks.py        # /bookmarks, /export
│   │   ├── files.py            # Загрузка документов (RAG)
│   │   ├── images.py           # OCR фотографий
│   │   ├── search.py           # /search
│   │   ├── memory.py           # /memory — факты о пользователе
│   │   ├── debate.py           # Режим дебатов AI
│   │   └── settings.py         # /settings — настройки пользователя
│   │
│   ├── keyboards/              # Конструкторы inline/reply клавиатур
│   │   ├── main_menu.py        # Reply-клавиатура (нижнее меню)
│   │   ├── model_select.py     # Переключение модели + кнопки ответа
│   │   ├── imagegen.py         # Управление генерацией изображений
│   │   ├── translator.py       # Клавиатура режима перевода
│   │   ├── youtube.py          # Клавиатуры действий YouTube
│   │   └── settings.py         # Клавиатура настроек
│   │
│   ├── middlewares/
│   │   └── auth.py             # Белый список по ADMIN_IDS
│   │
│   ├── models/                 # ORM-модели SQLAlchemy
│   │   ├── conversation.py     # История чата
│   │   ├── context_summary.py  # Суммаризованный контекст
│   │   ├── user_settings.py    # Настройки пользователя
│   │   ├── bookmark.py         # Сохранённые ответы
│   │   ├── memory.py           # Факты о пользователе
│   │   ├── embedding.py        # RAG-эмбеддинги документов
│   │   ├── file.py             # Метаданные загруженных файлов
│   │   ├── translator.py       # Глоссарий + память переводов
│   │   ├── service_balance.py  # Трекер расходов API
│   │   ├── pronunciation_rule.py
│   │   └── stress_override.py
│   │
│   ├── services/               # Бизнес-логика
│   │   ├── ai_router.py        # Маршрутизация к GPT/Claude/Gemini
│   │   ├── openai_service.py   # OpenAI chat completions
│   │   ├── anthropic_service.py # Claude messages API
│   │   ├── gemini_service.py   # Gemini generate_content
│   │   ├── streaming_service.py # Стриминг в реальном времени в Telegram
│   │   ├── context_service.py  # Окно контекста + суммаризация
│   │   ├── memory_service.py   # Извлечение фактов + хранение
│   │   ├── search_service.py   # Веб-поиск Tavily
│   │   ├── rag_service.py      # Эмбеддинги + векторный поиск
│   │   ├── translator_service.py # Логика перевода
│   │   ├── voice_service.py    # TTS + STT
│   │   ├── tts_pipeline.py     # Нормализация текста для TTS
│   │   ├── image_service.py    # DALL-E / Imagen / Flux
│   │   ├── youtube_service.py  # yt-dlp + субтитры
│   │   ├── bookmark_service.py # CRUD закладок
│   │   ├── export_service.py   # Экспорт диалога (MD/JSON/PDF)
│   │   ├── balance_service.py  # Трекер расходов
│   │   ├── settings_service.py # CRUD настроек пользователя
│   │   ├── telegraph_service.py # Длинный текст → Telegraph
│   │   ├── file_service.py     # Хранение файлов
│   │   └── debate_service.py   # Оркестрация дебатов AI
│   │
│   ├── utils/
│   │   ├── formatting.py       # Конвертер Markdown → Telegram HTML
│   │   └── prompts.py          # Централизованные системные промпты
│   │
│   └── data/
│       └── yo.dat              # Словарь ёфикации
│
├── alembic/                    # Миграции базы данных
├── prompts/                    # Внешние файлы промптов
│   ├── akida.txt               # Промпт перевода исламской акыды
│   └── fiqh.txt                # Промпт перевода исламского фикха
├── scripts/
│   └── backup_db.sh            # Ежедневный бэкап PostgreSQL
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

---

### Установка

#### Требования

- Docker + Docker Compose
- API-ключи: OpenAI, Anthropic, Google AI
- Токен Telegram-бота от [@BotFather](https://t.me/BotFather)
- (Опционально) Ключ Tavily API, ключ BFL API
- (Опционально) SOCKS5/HTTP-прокси для заблокированных регионов

#### Настройка

```bash
# Клонирование
git clone https://github.com/YOUR_USER/multi-ai-bot.git
cd multi-ai-bot

# Конфигурация
cp .env.example .env
nano .env  # Заполните API-ключи

# Запуск
docker compose up -d

# Проверка логов
docker logs -f multi_ai_bot
```

#### Прокси (для заблокированных регионов)

Если IP вашего сервера заблокирован Google AI или другими провайдерами, настройте прокси (например, XRay/VLESS) и добавьте в `.env` или `docker-compose.yml`:

```yaml
environment:
  HTTP_PROXY: http://127.0.0.1:10809
  HTTPS_PROXY: http://127.0.0.1:10809
```

Бот использует `network_mode: host` для доступа к сети хоста, включая прокси на localhost.

---

### Сервисы

#### AI-маршрутизатор (`ai_router.py`)
Направляет сообщения пользователя выбранному AI-провайдеру. Поддерживает выбор модели для каждого пользователя (сохраняется в БД) и режим "Спросить всех".

#### Стриминг (`streaming_service.py`)
Отправляет ответы AI токен за токеном с курсором (`▌`), обновляя сообщение в Telegram каждую 1 секунду. При ошибке HTML-парсинга откатывается на простой текст. Автоматически публикует в Telegraph ответы длиннее 3800 символов.

#### Контекст (`context_service.py`)
Поддерживает скользящее окно в 20 сообщений. При превышении старые сообщения суммаризируются AI и сохраняются как одно системное сообщение, сохраняя связность диалога и экономя токены.

#### Память (`memory_service.py`)
Автоматически извлекает факты о пользователе из диалогов (имя, предпочтения, интересы). Факты категоризируются и всегда включаются в системный промпт.

#### Переводчик (`translator_service.py`)
Двунаправленный перевод RU↔AR со специализированными промптами, пользовательским глоссарием (хранится как pgvector-эмбеддинги для нечёткого поиска) и памятью переводов.

#### Голос (`voice_service.py` + `tts_pipeline.py`)
STT через OpenAI Whisper. TTS через OpenAI gpt-4o-mini-tts с полным пайплайном нормализации: раскрытие чисел, ёфикация, расстановка ударений (russtress + пользовательские переопределения), словарь произношений.

#### YouTube (`youtube_service.py`)
Работает на yt-dlp с аутентификацией через cookies и решателем EJS-задач на Node.js. Извлекает информацию о видео, субтитры (youtube-transcript-api), скачивает видео/аудио с прогресс-барами в реальном времени.

#### Баланс (`balance_service.py`)
Отслеживает расходы по каждому API-сервису на основе использования токенов с ценами для каждой модели.

---

### Стоимость API (за 1M токенов)

| Модель | Вход | Выход |
|--------|------|-------|
| GPT-5.2 | $1.75 | $14.00 |
| Claude Opus 4.6 | $15.00 | $75.00 |
| Gemini 3 Pro | $1.25 | $10.00 |

| Сервис | Цена |
|--------|------|
| Whisper STT | $0.006/мин |
| TTS (gpt-4o-mini-tts) | $0.60/1M символов |
| DALL-E 3 (1024x1024) | $0.040/изображение |
| DALL-E 3 HD | $0.080/изображение |
| Gemini Imagen 3 | $0.040/изображение |
| Flux 2 Pro | $0.050/изображение |
| Эмбеддинги (text-embedding-3-small) | $0.020/1M токенов |
| Поиск Tavily | Бесплатный тариф: 1000 запросов/мес |

---

### Команды бота

| Команда | Описание |
|---------|----------|
| `/model` | Переключение AI-модели (GPT / Claude / Gemini / Все) |
| `/search` | Веб-поиск через Tavily |
| `/imagine` | Генерация изображений (DALL-E 3 / Imagen / Flux) |
| `/memory` | Просмотр/управление фактами о вас |
| `/bookmarks` | Просмотр сохранённых ответов AI |
| `/export` | Экспорт диалога (Markdown / JSON / PDF) |
| `/balance` | Проверка расходов API |
| `/pronounce` | Управление словарём произношений TTS |
| `/fix` | Управление переопределениями ударений |
| `/glossary` | Управление глоссарием переводчика |
| `/translator_prompt` | Управление промптами переводчика |
| `/context` | Статистика окна контекста |
| `/clear` | Очистить историю диалога |
| `/help` | Показать все команды |

**Inline-кнопки под ответами:** Перегенерировать, Спросить другую модель, Озвучить, Сохранить.

**Кнопки меню:** Модель, Переводчик, Генерация, Баланс, Контекст, Очистить.

---

### Бэкапы

Автоматический ежедневный бэкап PostgreSQL через cron (3:00 ночи):

```bash
# Ручной бэкап
./scripts/backup_db.sh

# Бэкапы хранятся в /media/hdd/ai-bot/backups/
# Хранение: 7 дней
```

---

### Планы развития

- [ ] Скрипт автоустановки для развёртывания в один клик
- [ ] Веб-панель для настроек и аналитики
- [ ] Мультипользовательский режим с раздельными квотами
- [ ] Отложенные сообщения / напоминания
- [ ] Система плагинов для кастомных обработчиков
- [ ] Локальный Bot API сервер для загрузки больших файлов

---

### Лицензия

Лицензия MIT. Подробнее в файле [LICENSE](LICENSE).
