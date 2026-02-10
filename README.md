# Multi-AI Telegram Bot

Personal Telegram bot that combines **GPT**, **Claude**, and **Gemini** in one interface with streaming responses, voice synthesis, image generation, web search, RAG, translation, YouTube tools, and more.

> Built for personal use. One bot — all AI models, switchable on the fly.

---

## Features

### Core AI
| Feature | Description |
|---------|-------------|
| **3 AI Models** | GPT-5.2, Claude Opus 4.6, Gemini 3 Pro — switch instantly |
| **Streaming** | Real-time token-by-token output with cursor animation |
| **"Ask All"** | Send one message to all 3 models, get 3 responses side by side |
| **Smart Context** | 20-message sliding window + automatic summarization of older context |
| **Memory** | Bot remembers facts about you (name, preferences) across sessions |
| **Model Persistence** | Selected model saved per user in database |

### Search & RAG
| Feature | Description |
|---------|-------------|
| **Web Search** | Tavily-powered search with auto-detection of search queries |
| **RAG** | Upload PDF/DOCX/XLSX/TXT/images — bot extracts text, chunks, embeds with pgvector, retrieves relevant context |
| **Image OCR** | Extract text from photos (PyMuPDF, python-docx, openpyxl) |

### Voice
| Feature | Description |
|---------|-------------|
| **Voice Input** | Whisper STT — send voice message, get text + AI response |
| **TTS** | OpenAI TTS (gpt-4o-mini-tts) with per-model voices (ash/onyx/echo) |
| **TTS Pipeline** | Text normalization, yofikation, stress placement (russtress), custom pronunciation dictionary |

### Translation (RU / AR)
| Feature | Description |
|---------|-------------|
| **Bidirectional** | Russian to Arabic / Arabic to Russian |
| **Input modes** | Text, voice messages, photos (OCR), documents |
| **3-Model Compare** | Translate with one model, then instantly compare all 3 |
| **Custom prompts** | Specialized prompts for Islamic terminology (Aqeedah, Fiqh) |
| **Glossary** | Per-user glossary with pgvector similarity search |
| **Translation Memory** | Stores previous translations, finds similar segments |

### Image Generation
| Feature | Description |
|---------|-------------|
| **DALL-E 3** | With size/style/quality controls |
| **Gemini Imagen 3** | Google's image model |
| **Flux 2 Pro** | Black Forest Labs model |
| **Inline controls** | Switch provider, size, style, regenerate — all via buttons |

### YouTube
| Feature | Description |
|---------|-------------|
| **Video info** | Send YouTube link — get title, channel, duration |
| **AI Summary** | Full transcript extraction + AI summarization |
| **Download video** | Choose quality (360p-1080p), progress bar |
| **Download audio** | MP3 128/320 kbps or WAV, FFmpeg conversion with progress |

### Utilities
| Feature | Description |
|---------|-------------|
| **Bookmarks** | Save any AI response, add notes, search, paginated list |
| **Export** | Export full dialog as Markdown, JSON, or PDF |
| **Telegraph** | Long responses (>3800 chars) auto-published to Telegraph |
| **Balance tracker** | Per-service spending tracking with token-level pricing |
| **Debate mode** | Two AI models debate a topic you choose |

---

## Architecture

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

## Tech Stack

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

## Project Structure

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

## Installation

### Prerequisites

- Docker + Docker Compose
- API keys: OpenAI, Anthropic, Google AI
- Telegram bot token from [@BotFather](https://t.me/BotFather)
- (Optional) Tavily API key, BFL API key
- (Optional) SOCKS5/HTTP proxy for restricted regions

### Setup

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

### Proxy (for restricted regions)

If your server's IP is blocked by Google AI or other providers, set up a proxy (e.g., XRay/VLESS) and add to `.env` or `docker-compose.yml`:

```yaml
environment:
  HTTP_PROXY: http://127.0.0.1:10809
  HTTPS_PROXY: http://127.0.0.1:10809
```

The bot uses `network_mode: host` to share the host's network stack, including any localhost proxies.

---

## Services

### AI Router (`ai_router.py`)
Routes user messages to the selected AI provider. Supports per-user model selection (saved in DB) and "Ask All" mode.

### Streaming (`streaming_service.py`)
Sends AI responses token-by-token with a cursor (`▌`), updating the Telegram message every 1 second. Falls back to plain text if HTML parsing fails. Auto-publishes to Telegraph for responses >3800 characters.

### Context (`context_service.py`)
Maintains a 20-message sliding window. When exceeded, older messages are summarized by AI and stored as a single system message, preserving conversation coherence while saving tokens.

### Memory (`memory_service.py`)
Automatically extracts facts about the user from conversations (name, preferences, interests). Facts are categorized and always included in the system prompt.

### Translator (`translator_service.py`)
Bidirectional RU↔AR translation with specialized prompts, per-user glossary (stored as pgvector embeddings for fuzzy matching), and translation memory.

### Voice (`voice_service.py` + `tts_pipeline.py`)
STT via OpenAI Whisper. TTS via OpenAI gpt-4o-mini-tts with a full normalization pipeline: number expansion, yofikation, stress placement (russtress + custom overrides), pronunciation dictionary.

### YouTube (`youtube_service.py`)
Powered by yt-dlp with cookie authentication and Node.js EJS challenge solver. Extracts video info, transcripts (youtube-transcript-api), downloads video/audio with real-time progress bars.

### Balance (`balance_service.py`)
Tracks spending per API service based on token usage with per-model pricing.

---

## API Costs (per 1M tokens)

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

## Bot Commands

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

## Backups

Automatic daily PostgreSQL backups via cron (3:00 AM):

```bash
# Manual backup
./scripts/backup_db.sh

# Backups stored in /media/hdd/ai-bot/backups/
# Retention: 7 days
```

---

## Roadmap

- [ ] Auto-install script for one-click deployment
- [ ] Web dashboard for settings and analytics
- [ ] Multi-user support with separate quotas
- [ ] Scheduled messages / reminders
- [ ] Plugin system for custom handlers
- [ ] Local Bot API server for large file uploads

---

## License

MIT License. See [LICENSE](LICENSE) for details.
