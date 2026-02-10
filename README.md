# Multi-AI Telegram Bot

<div align="center">

```
  __  __       _ _   _        _    ___   ____        _
 |  \/  |_   _| | |_(_)      / \  |_ _| | __ )  ___ | |_
 | |\/| | | | | | __| |____ / _ \  | |  |  _ \ / _ \| __|
 | |  | | |_| | | |_| |____/ ___ \ | |  | |_) | (_) | |_
 |_|  |_|\__,_|_|\__|_|   /_/   \_\___| |____/ \___/ \__|
```

**GPT + Claude + Gemini | Streaming | TTS | RAG | YouTube | Translation | Image Gen**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/)
[![aiogram 3.x](https://img.shields.io/badge/aiogram-3.x-green.svg)](https://docs.aiogram.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://docs.docker.com/compose/)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16+pgvector-blue.svg)](https://github.com/pgvector/pgvector)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**[English](#english) | [Русский](#русский)**

</div>

---

<a id="english"></a>

## English

A production-grade Telegram bot that combines **GPT**, **Claude**, and **Gemini** in one interface with real-time streaming, voice synthesis, image generation, web search, RAG document analysis, RU↔AR translation, YouTube tools, multi-user quotas, and a Local Bot API server for 2GB file uploads.

> One bot — all AI models, switchable on the fly. Built for daily use with full infrastructure: proxy routing, backups, auto-installer, and quota management.

---

### Table of Contents

- [Features](#features)
  - [Core AI](#core-ai)
  - [Search & RAG](#search--rag)
  - [Voice](#voice)
  - [Translation (RU ↔ AR)](#translation-ru--ar)
  - [Image Generation](#image-generation)
  - [YouTube](#youtube)
  - [Multi-User Quotas](#multi-user-quotas)
  - [Utilities](#utilities)
- [Architecture](#architecture)
  - [System Diagram](#system-diagram)
  - [Key Design Decisions](#key-design-decisions)
  - [Docker Services](#docker-services)
  - [Local Bot API & Proxychains](#local-bot-api--proxychains)
  - [Proxy Routing (XRay/VLESS)](#proxy-routing-xrayvless)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Installation](#installation)
  - [Auto-Install (Recommended)](#auto-install-recommended)
  - [Manual Install](#manual-install)
  - [Proxy Setup](#proxy-setup-for-restricted-regions)
  - [Local Bot API Setup](#local-bot-api-setup)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Model Defaults](#model-defaults)
  - [RAG Settings](#rag-settings)
  - [Voice Settings](#voice-settings)
- [Bot Commands](#bot-commands)
- [Services Deep Dive](#services-deep-dive)
- [Quota System](#quota-system)
- [API Costs](#api-costs)
- [Database](#database)
- [Backups](#backups)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [License](#license)

---

### Features

#### Core AI

| Feature | Description |
|---------|-------------|
| **3 AI Models** | GPT-5.2, Claude Opus 4.6, Gemini 3 Pro — switch instantly via inline buttons or `/model` |
| **Streaming** | Real-time token-by-token output with cursor animation (`▌`), message updates every 1 second |
| **"Ask All"** | Send one message to all 3 models simultaneously, get 3 separate responses side by side |
| **Smart Context** | 20-message sliding window with automatic AI summarization of older messages to preserve coherence |
| **Memory** | Bot automatically extracts and remembers facts about you (name, preferences, interests) across all sessions |
| **Model Persistence** | Selected model saved per user in PostgreSQL, persists across bot restarts |
| **Telegraph** | Responses longer than 3800 characters auto-published to Telegraph with "Read full" button |
| **Signature** | Every response has a signature: `— Model Name | date` in a blockquote |

#### Search & RAG

| Feature | Description |
|---------|-------------|
| **Web Search** | Tavily-powered search with smart auto-detection of queries that need web data |
| **Auto-Search Triggers** | Keywords like "найди", "сколько стоит", "новости", "что случилось" auto-trigger search |
| **RAG** | Upload PDF/DOCX/XLSX/CSV/TXT/images → text extraction → chunking → pgvector embeddings → semantic retrieval |
| **Chunk Settings** | Configurable chunk size (800), overlap (100), and top-K retrieval (5) |
| **Image OCR** | Send photos → text extraction via PyMuPDF + python-docx + openpyxl |

#### Voice

| Feature | Description |
|---------|-------------|
| **Voice Input** | OpenAI Whisper STT — send voice message, get transcription + AI response |
| **TTS** | OpenAI gpt-4o-mini-tts with per-model voices: `ash` (GPT), `onyx` (Claude), `echo` (Gemini) |
| **TTS Pipeline** | Full normalization chain: number expansion (num2words) → yofikation (ё restoration) → stress marks (russtress + TensorFlow) → custom pronunciation dictionary |
| **Pronunciation Dict** | `/pronounce` — add/edit/delete custom word pronunciations for TTS |
| **Stress Overrides** | `/fix` — override automatic stress placement for specific words |
| **Voice-to-Search** | Voice messages can trigger web search if query detected |

#### Translation (RU ↔ AR)

| Feature | Description |
|---------|-------------|
| **Bidirectional** | Russian → Arabic and Arabic → Russian with auto-direction detection |
| **4 Input Modes** | Text messages, voice messages (STT→translate), photos (OCR→translate), documents |
| **3-Model Compare** | Translate with one model, then instantly compare translations from all 3 models |
| **Islamic Terminology** | Specialized prompts for Aqeedah and Fiqh terminology with proper transliteration |
| **Custom Prompts** | `/translator_prompt` — create and switch between multiple translation system prompts |
| **Glossary** | `/glossary` — per-user glossary with pgvector similarity search for fuzzy matching |
| **Translation Memory** | Stores all translations, finds similar segments to improve consistency |
| **Mode Switching** | Enter/exit translator mode via menu button, direction switch via inline buttons |

#### Image Generation

| Feature | Description |
|---------|-------------|
| **3 Providers** | DALL-E 3, Gemini Imagen 3, Flux 2 Pro (Black Forest Labs) |
| **DALL-E 3 Controls** | Size (1024x1024, 1792x1024, 1024x1792), style (vivid/natural), quality (standard/hd) |
| **Gemini Imagen** | Google's image generation model via Gemini API |
| **Flux 2 Pro** | Via BFL API with custom sizes |
| **Inline Controls** | Switch provider, size, style, quality, regenerate — all via inline keyboard buttons |
| **Quota Tracking** | Image generation counts toward daily user quota |

#### YouTube

| Feature | Description |
|---------|-------------|
| **Auto-Detection** | Send any YouTube link — bot auto-detects and shows action buttons |
| **Video Info** | Title, channel, duration, view count, thumbnail |
| **AI Summary** | Full transcript extraction (youtube-transcript-api) + chunked AI summarization for long videos |
| **Q&A Mode** | "Ask about video" — ask questions about video content using transcript as context |
| **Video Download** | Choose quality (360p/480p/720p/1080p), real-time progress bar with ETA |
| **Audio Download** | MP3 (128/320 kbps) or WAV, FFmpeg conversion with progress |
| **Large Files** | With Local Bot API: up to 2GB files. Warning at 200MB+ about upload time |
| **Quota Gating** | YouTube download requires Basic or Pro plan |

#### Multi-User Quotas

| Feature | Description |
|---------|-------------|
| **Auto-Registration** | Users auto-registered on first message to the bot |
| **3 Plans** | `free` (10K tokens/day, 3 images/day, no YouTube), `basic` (100K tokens, 20 images, YouTube), `pro` (unlimited) |
| **Daily Reset** | Counters reset at midnight automatically (inline check, no background scheduler) |
| **Token Tracking** | Actual tokens counted after each AI call |
| **Image Tracking** | Image generation counted per successful generation |
| **YouTube Gating** | YouTube download locked to Basic/Pro plans |
| **`/plan`** | View current plan, usage statistics, limits |
| **`/setplan`** | Admin-only: set user plan by Telegram ID |
| **In-Memory Cache** | User data cached in memory to avoid DB queries on every message |

#### Utilities

| Feature | Description |
|---------|-------------|
| **Bookmarks** | Save any AI response with `/bookmark`, add notes, search, paginated list |
| **Export** | Export full dialog as Markdown, JSON, or PDF via `/export` |
| **Balance Tracker** | Per-service API spending tracking with token-level pricing for all services |
| **Debate Mode** | Two AI models debate a topic you choose, with rounds and summary |
| **Settings** | `/settings` — configure default model, voice, style, auto-search, auto-memory |
| **Context Stats** | `/context` — view current context window usage, message count, summary status |

---

### Architecture

#### System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Docker Host                              │
│                                                                  │
│  ┌─────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │ telegram-bot-│    │    Bot (Python)   │    │  PostgreSQL   │  │
│  │ api (Local)  │    │  network_mode:    │    │  16 + pgvector│  │
│  │  :8081       │◄───│     host          │───►│  :5432        │  │
│  │  proxychains │    │  HTTP_PROXY ───┐  │    │               │  │
│  │  ──► XRay    │    │               │  │    │  Tables:       │  │
│  └──────┬───────┘    └──────────┬────┘  │    │  conversations │  │
│         │                       │       │    │  users         │  │
│         │  MTProto              │       │    │  embeddings    │  │
│         ▼                       ▼       │    │  memories      │  │
│  ┌──────────────┐    ┌──────────────┐   │    │  bookmarks     │  │
│  │  Telegram DC  │    │  XRay/VLESS  │◄──┘    │  ...           │  │
│  │  (via Latvia  │    │  :10809 HTTP │        └───────────────┘  │
│  │   proxy)      │    │  :10808 SOCKS│                           │
│  └──────────────┘    │              │                            │
│                      │  Outbound:   │                            │
│                      │  Latvia (def)│──► OpenAI, Anthropic       │
│                      │  USA (Google)│──► Google AI API            │
│                      └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Design Decisions

| Decision | Why |
|----------|-----|
| `network_mode: host` for bot | Access XRay proxy on `127.0.0.1:10809` without Docker networking complexity |
| `network_mode: host` for telegram-bot-api | Same reason — proxychains needs to reach XRay on localhost |
| Dual XRay outbound | Latvia (default) + USA for Google AI API (Google blocks Russia/Latvia for Gemini) |
| `proxychains-ng` for Local Bot API | TDLib (MTProto) ignores HTTP_PROXY env vars. proxychains intercepts `connect()` syscalls via LD_PRELOAD |
| Inline daily reset | No background scheduler needed — quotas reset lazily when user sends next message |
| In-memory quota cache | Avoid DB query on every message; cache invalidated on plan change or daily reset |
| aiogram DI | All services injected into Dispatcher, handlers receive them as parameters |
| Async throughout | asyncpg, httpx, aiohttp — no blocking calls |
| Streaming via edit_text | 1-second throttle prevents Telegram rate limit (30 edits/min) |
| pgvector for RAG + glossary | Single DB handles both relational data and vector similarity search |

#### Docker Services

| Service | Container | Image | Network | Purpose |
|---------|-----------|-------|---------|---------|
| `bot` | `multi_ai_bot` | Custom (Python 3.12) | `host` | Main bot process |
| `db` | `multi_ai_bot_db` | `pgvector/pgvector:pg16` | `bridge` (port 5432) | PostgreSQL + pgvector |
| `telegram-bot-api` | `telegram_bot_api` | Custom (proxychains) | `host` | Local Telegram Bot API server |

#### Local Bot API & Proxychains

The Local Bot API server (`telegram-bot-api`) allows uploading files up to **2GB** (vs 50MB with Cloud API). It runs a TDLib-based server that communicates directly with Telegram DC servers via MTProto protocol.

**Problem:** TDLib doesn't support HTTP_PROXY/HTTPS_PROXY environment variables for MTProto connections. On servers where Telegram DC IPs are blocked (e.g., Russia), the server can't connect.

**Solution:** Custom Docker image with `proxychains-ng`:

```
telegram-bot-api/
├── Dockerfile              # Based on aiogram/telegram-bot-api:latest
│                           # + apk add proxychains-ng
│                           # + proxychains.conf → http 127.0.0.1 10809
└── entrypoint-proxy.sh     # exec proxychains4 -q /docker-entrypoint.sh "$@"
```

`proxychains-ng` intercepts ALL `connect()` system calls via `LD_PRELOAD`, routing every TCP connection through the XRay HTTP proxy — including MTProto.

#### Proxy Routing (XRay/VLESS)

```
XRay config: /usr/local/etc/xray/config.json

Inbound:
  - HTTP proxy  → 127.0.0.1:10809
  - SOCKS5      → 127.0.0.1:10808

Outbound (VLESS):
  - Latvia  (62.192.174.164)  ← default for all traffic
  - USA     (45.158.127.7)    ← routed via domain rules

Routing rules:
  - *googleapis.com  → USA outbound (Google blocks AI API from Latvia/RU)
  - *google.com      → USA outbound
  - Everything else   → Latvia outbound
```

The bot container sets `HTTP_PROXY=http://127.0.0.1:10809` and `HTTPS_PROXY=http://127.0.0.1:10809`. OpenAI/Anthropic SDKs use `httpx` which automatically picks up these environment variables.

---

### Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Bot framework | [aiogram](https://docs.aiogram.dev/) | 3.4+ |
| Language | Python | 3.12 |
| Database | PostgreSQL + [pgvector](https://github.com/pgvector/pgvector) | 16 |
| ORM | SQLAlchemy (async) | 2.0+ |
| Migrations | Alembic | 1.13+ |
| AI: GPT | [OpenAI SDK](https://github.com/openai/openai-python) | 1.12+ |
| AI: Claude | [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python) | 0.18+ |
| AI: Gemini | [Google GenAI SDK](https://github.com/googleapis/python-genai) | 1.0+ |
| Web search | [Tavily API](https://tavily.com/) | 0.5+ |
| Embeddings | OpenAI text-embedding-3-small | — |
| TTS | OpenAI gpt-4o-mini-tts | — |
| STT | OpenAI Whisper | — |
| Stress marks | [russtress](https://github.com/Ulitochka/russtress) + TensorFlow/Keras | 0.1.3 |
| Number-to-words | [num2words](https://github.com/savoirfairelinux/num2words) | 0.5.13 |
| Image gen | DALL-E 3, Gemini Imagen 3, [Flux 2 Pro](https://blackforestlabs.ai/) | — |
| YouTube | [yt-dlp](https://github.com/yt-dlp/yt-dlp) + [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) | 2024+ |
| PDF | [PyMuPDF](https://pymupdf.readthedocs.io/) | 1.24+ |
| Documents | [python-docx](https://python-docx.readthedocs.io/) + [openpyxl](https://openpyxl.readthedocs.io/) | — |
| Long text | [Telegraph API](https://telegra.ph/) | 2.2+ |
| Proxy SOCKS | [aiohttp-socks](https://github.com/romis2012/aiohttp-socks) + [httpx[socks]](https://www.python-httpx.org/) | — |
| Proxy tunnel | [proxychains-ng](https://github.com/rofl0r/proxychains-ng) | — |
| Container | Docker + Docker Compose | — |
| VPN/Proxy | XRay/VLESS (dual outbound) | — |
| Local Bot API | [telegram-bot-api](https://github.com/tdlib/telegram-bot-api) (aiogram image) | latest |

---

### Project Structure

```
multi-ai-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py                    # Entry point: Dispatcher, DI, router registration
│   ├── config.py                  # @dataclass Config with from_env() loader
│   ├── database.py                # SQLAlchemy async engine + session factory
│   │
│   ├── handlers/                  # Telegram message/callback handlers
│   │   ├── __init__.py
│   │   ├── chat.py                # Text → AI (single/all), regenerate, ask other model
│   │   ├── start.py               # /start, /help, /clear, /context, /balance, /plan, /setplan
│   │   ├── model_switch.py        # /model — AI provider selection
│   │   ├── translator.py          # Translator mode (RU↔AR), glossary, prompts
│   │   ├── voice.py               # Voice messages (STT → AI → optional TTS)
│   │   ├── imagegen.py            # /imagine — DALL-E 3 / Imagen / Flux
│   │   ├── youtube.py             # YouTube links — info, summary, download, Q&A
│   │   ├── bookmarks.py           # /bookmarks, save, notes, export
│   │   ├── files.py               # Document upload → RAG indexing
│   │   ├── images.py              # Photo OCR / Vision API analysis
│   │   ├── search.py              # /search — Tavily web search
│   │   ├── memory.py              # /memory — user facts management
│   │   ├── debate.py              # AI debate mode (2 models)
│   │   └── settings.py            # /settings — user preferences
│   │
│   ├── keyboards/                 # Inline/reply keyboard builders
│   │   ├── __init__.py
│   │   ├── main_menu.py           # Reply keyboard (bottom menu buttons)
│   │   ├── model_select.py        # Model switch + response action buttons
│   │   ├── imagegen.py            # Image gen control panel
│   │   ├── translator.py          # Translator mode keyboard
│   │   ├── youtube.py             # YouTube action buttons
│   │   └── settings.py            # Settings keyboard
│   │
│   ├── middlewares/
│   │   ├── __init__.py
│   │   └── auth.py                # Whitelist by ADMIN_IDS + auto-registration
│   │
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── __init__.py            # All model imports
│   │   ├── user.py                # User: plan, quotas, daily reset
│   │   ├── conversation.py        # Chat message history
│   │   ├── context_summary.py     # Summarized older context
│   │   ├── user_settings.py       # Per-user preferences
│   │   ├── bookmark.py            # Saved AI responses
│   │   ├── memory.py              # Facts about user
│   │   ├── embedding.py           # RAG document embeddings (pgvector)
│   │   ├── file.py                # Uploaded file metadata
│   │   ├── translator.py          # Glossary entries + translation memory
│   │   ├── service_balance.py     # API spending tracker
│   │   ├── pronunciation_rule.py  # TTS custom pronunciations
│   │   └── stress_override.py     # Stress mark overrides
│   │
│   ├── services/                  # Business logic layer
│   │   ├── __init__.py
│   │   ├── ai_router.py           # Routes requests to GPT/Claude/Gemini
│   │   ├── openai_service.py      # OpenAI: chat, embeddings, DALL-E, Whisper, TTS
│   │   ├── anthropic_service.py   # Claude: messages API, streaming, vision
│   │   ├── gemini_service.py      # Gemini: generate_content, vision, Imagen
│   │   ├── streaming_service.py   # Real-time streaming to Telegram + Telegraph
│   │   ├── context_service.py     # Context window + summarization
│   │   ├── memory_service.py      # Fact extraction + storage
│   │   ├── quota_service.py       # Plan-based quotas (tokens, images, YouTube)
│   │   ├── search_service.py      # Tavily web search
│   │   ├── rag_service.py         # Embeddings + vector similarity search
│   │   ├── translator_service.py  # Translation logic + glossary + TM
│   │   ├── voice_service.py       # TTS synthesis + STT transcription
│   │   ├── tts_pipeline.py        # Text normalization chain for TTS
│   │   ├── image_service.py       # DALL-E 3 / Gemini Imagen / Flux
│   │   ├── youtube_service.py     # yt-dlp + transcripts + download
│   │   ├── bookmark_service.py    # Bookmarks CRUD
│   │   ├── export_service.py      # Dialog export (Markdown/JSON/PDF)
│   │   ├── balance_service.py     # API spending tracker
│   │   ├── settings_service.py    # User settings CRUD
│   │   ├── telegraph_service.py   # Long text → Telegraph pages
│   │   ├── file_service.py        # File storage + metadata
│   │   └── debate_service.py      # AI debate orchestration
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── formatting.py          # Markdown → Telegram HTML converter
│   │   └── prompts.py             # Centralized system prompts
│   │
│   └── data/
│       └── yo.dat                 # Yofikation dictionary (ё restoration)
│
├── telegram-bot-api/              # Custom Local Bot API image
│   ├── Dockerfile                 # aiogram/telegram-bot-api + proxychains-ng
│   └── entrypoint-proxy.sh        # proxychains4 -q /docker-entrypoint.sh
│
├── alembic/                       # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                  # Migration scripts
│
├── prompts/                       # External prompt files
│   ├── akida.txt                  # Islamic Aqeedah translation prompt
│   └── fiqh.txt                   # Islamic Fiqh translation prompt
│
├── scripts/
│   └── backup_db.sh               # Daily PostgreSQL backup (cron)
│
├── docker-compose.yml             # 3 services: bot, db, telegram-bot-api
├── Dockerfile                     # Python 3.12 + ffmpeg + Node.js + yt-dlp
├── requirements.txt               # 23 Python dependencies
├── install.sh                     # Auto-installer script
├── alembic.ini                    # Alembic configuration
├── .env.example                   # Environment template with comments
├── .env                           # Local secrets (not in git)
├── .gitignore
├── .dockerignore
├── LICENSE                        # MIT License
└── README.md
```

---

### Installation

#### Auto-Install (Recommended)

The auto-installer handles everything: Docker check, directory creation, interactive API key setup, build, startup verification.

```bash
git clone https://github.com/Al-Zirr/multi-ai-bot.git
cd multi-ai-bot
chmod +x install.sh
./install.sh
```

The installer will:
1. Check/install Docker and Docker Compose
2. Create data directories (`/media/hdd/ai-bot/{files,logs,backups,telegram-api,yt-dlp-cache}`)
3. Copy `.env.example` → `.env` and interactively ask for all API keys
4. Auto-generate a strong database password
5. Ask if you want Local Bot API (2GB file limit)
6. Run `docker compose build` and `docker compose up -d`
7. Wait for PostgreSQL + bot startup and verify everything works
8. Enable pgvector extension
9. Show summary with container status, configured API keys, and useful commands

#### Manual Install

```bash
# 1. Clone
git clone https://github.com/Al-Zirr/multi-ai-bot.git
cd multi-ai-bot

# 2. Configure
cp .env.example .env
nano .env                    # Fill in API keys

# 3. Create directories
mkdir -p /media/hdd/ai-bot/{files,logs,backups,telegram-api,yt-dlp-cache}

# 4. Build and start
docker compose up -d --build

# 5. Enable pgvector extension
source .env
PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" \
    -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 6. Create users table (if not using Alembic)
PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" -c "
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(100),
    plan VARCHAR(20) NOT NULL DEFAULT 'free',
    tokens_used INT NOT NULL DEFAULT 0,
    tokens_limit INT NOT NULL DEFAULT 10000,
    images_used INT NOT NULL DEFAULT 0,
    images_limit INT NOT NULL DEFAULT 3,
    usage_reset_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    expires_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_users_telegram_id ON users(telegram_id);
"

# 7. Check logs
docker logs -f multi_ai_bot
```

#### Prerequisites

| Requirement | Notes |
|-------------|-------|
| Docker + Docker Compose v2 | Auto-installed by `install.sh` |
| Telegram Bot Token | From [@BotFather](https://t.me/BotFather) |
| At least 1 AI API key | OpenAI / Anthropic / Google AI |
| Telegram API ID + Hash | From [my.telegram.org](https://my.telegram.org) (required for Local Bot API) |
| (Optional) Tavily API key | For web search. Free tier: 1000 req/month |
| (Optional) BFL API key | For Flux 2 Pro image generation |
| (Optional) HTTP/SOCKS proxy | For restricted regions (Russia, Iran, etc.) |

#### Proxy Setup (for restricted regions)

If your server can't reach AI APIs directly (e.g., Google blocks Russian IPs), set up XRay/VLESS or any HTTP proxy:

```yaml
# docker-compose.yml — bot service
environment:
  HTTP_PROXY: http://127.0.0.1:10809
  HTTPS_PROXY: http://127.0.0.1:10809
```

The bot uses `network_mode: host`, so it shares the host's network and can reach any localhost proxy.

For **dual-outbound** routing (different proxies for different AI providers):

```json
// XRay routing rule example
{
  "type": "field",
  "domain": ["googleapis.com", "google.com", "generativelanguage.googleapis.com"],
  "outboundTag": "usa-outbound"
}
```

#### Local Bot API Setup

Local Bot API allows file uploads up to **2GB** (vs 50MB with Cloud API).

1. Set in `.env`:
```bash
USE_LOCAL_API=true
LOCAL_API_URL=http://127.0.0.1:8081
TELEGRAM_API_ID=your_api_id       # from my.telegram.org
TELEGRAM_API_HASH=your_api_hash   # from my.telegram.org
```

2. The `telegram-bot-api` service is already configured in `docker-compose.yml`. It builds a custom image with `proxychains-ng` that tunnels MTProto through your proxy.

3. Restart:
```bash
docker compose up -d --build telegram-bot-api
```

4. Verify:
```bash
curl --noproxy '*' "http://127.0.0.1:8081/bot<YOUR_TOKEN>/getMe"
# Should return {"ok":true,"result":{...}}
```

**If you DON'T need Local API** (no proxy issues, no large files), set `USE_LOCAL_API=false` in `.env` — the bot will use Telegram Cloud API.

---

### Configuration

#### Environment Variables

All settings are in `.env`. Full reference:

```bash
# ═══════════════ Telegram ═══════════════
BOT_TOKEN=                    # Bot token from @BotFather
TELEGRAM_API_ID=              # api_id from my.telegram.org
TELEGRAM_API_HASH=            # api_hash from my.telegram.org
ADMIN_IDS=                    # Comma-separated Telegram user IDs
USE_LOCAL_API=false            # true = Local Bot API, false = Cloud API
LOCAL_API_URL=http://127.0.0.1:8081

# ═══════════════ AI Models ═══════════════
OPENAI_API_KEY=               # GPT, TTS, STT, DALL-E, embeddings
ANTHROPIC_API_KEY=            # Claude
GOOGLE_AI_API_KEY=            # Gemini

# ═══════════════ Model Defaults ═══════════════
DEFAULT_GPT_MODEL=gpt-5.2
DEFAULT_CLAUDE_MODEL=claude-opus-4-6
DEFAULT_GEMINI_MODEL=gemini-3-pro-preview
DEFAULT_MODEL=claude           # Default provider: gpt / claude / gemini

# ═══════════════ Database ═══════════════
DB_HOST=127.0.0.1
DB_PORT=5432
DB_USER=multi_ai_bot
DB_PASSWORD=                   # Strong password (auto-generated by install.sh)
DB_NAME=multi_ai_bot

# ═══════════════ Streaming ═══════════════
STREAMING_ENABLED=true
STREAMING_UPDATE_INTERVAL=1.0  # Seconds between Telegram edits

# ═══════════════ Context ═══════════════
MAX_CONTEXT_MESSAGES=20        # Before summarization kicks in

# ═══════════════ Search ═══════════════
TAVILY_API_KEY=                # Tavily web search API key
AUTO_SEARCH=true               # Auto-detect search queries

# ═══════════════ RAG / Embeddings ═══════════════
EMBEDDING_MODEL=text-embedding-3-small
RAG_CHUNK_SIZE=800
RAG_CHUNK_OVERLAP=100
RAG_TOP_K=5

# ═══════════════ Voice ═══════════════
TTS_VOICE_GPT=ash              # Voice for GPT responses
TTS_VOICE_CLAUDE=onyx          # Voice for Claude responses
TTS_VOICE_GEMINI=echo          # Voice for Gemini responses

# ═══════════════ Image Generation ═══════════════
BFL_API_KEY=                   # Black Forest Labs (Flux 2 Pro)

# ═══════════════ Files ═══════════════
FILES_DIR=/app/files           # Inside container
```

#### Model Defaults

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_GPT_MODEL` | `gpt-5.2` | OpenAI model for GPT responses |
| `DEFAULT_CLAUDE_MODEL` | `claude-opus-4-6` | Anthropic model for Claude responses |
| `DEFAULT_GEMINI_MODEL` | `gemini-3-pro-preview` | Google model for Gemini responses |
| `DEFAULT_MODEL` | `claude` | Default AI provider for new users (`gpt`/`claude`/`gemini`) |

#### RAG Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `RAG_CHUNK_SIZE` | `800` | Characters per document chunk |
| `RAG_CHUNK_OVERLAP` | `100` | Overlap between adjacent chunks |
| `RAG_TOP_K` | `5` | Number of relevant chunks to retrieve |

#### Voice Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `TTS_VOICE_GPT` | `ash` | Voice for GPT TTS |
| `TTS_VOICE_CLAUDE` | `onyx` | Voice for Claude TTS |
| `TTS_VOICE_GEMINI` | `echo` | Voice for Gemini TTS |

Available voices: `alloy`, `ash`, `ballad`, `coral`, `echo`, `fable`, `nova`, `onyx`, `sage`, `shimmer`

---

### Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start bot, show welcome message |
| `/help` | Show all available commands |
| `/model` | Switch AI model (GPT / Claude / Gemini / All) |
| `/search [query]` | Web search via Tavily |
| `/imagine [prompt]` | Generate images (DALL-E 3 / Imagen / Flux) |
| `/memory` | View and manage stored facts about you |
| `/bookmarks` | View saved AI responses |
| `/export` | Export dialog (Markdown / JSON / PDF) |
| `/balance` | Check API spending per service |
| `/plan` | View your plan, quota usage, limits |
| `/setplan [user_id] [plan]` | Admin: set user plan (free/basic/pro) |
| `/setbalance [service] [amount]` | Admin: set API balance |
| `/pronounce` | Manage TTS pronunciation dictionary |
| `/fix` | Manage stress mark overrides |
| `/glossary` | Manage translator glossary terms |
| `/translator_prompt` | Manage custom translator prompts |
| `/context` | View context window statistics |
| `/settings` | Configure user preferences |
| `/clear` | Clear conversation history |

**Inline buttons under each AI response:**

| Button | Action |
|--------|--------|
| Regenerate (🔄) | Re-send the same prompt to get a different response |
| GPT / Claude / Gemini | Re-ask the same question using a different model |
| All models | Get responses from all 3 models |
| TTS (🔊) | Convert the response to voice |
| Bookmark (🔖) | Save the response |

**Reply keyboard (bottom menu):**

| Button | Action |
|--------|--------|
| Модель | Quick model switch |
| Переводчик | Enter/exit translator mode |
| Генерация | `/imagine` shortcut |
| Баланс | `/balance` shortcut |
| Контекст | `/context` shortcut |
| Очистить | `/clear` shortcut |

---

### Services Deep Dive

#### AI Router (`ai_router.py`)

Central dispatcher that routes user messages to the active AI provider. Maintains instances of `OpenAIService`, `AnthropicService`, and `GeminiService`. Supports:
- Per-user model selection (stored in DB)
- "Ask All" mode — sends to all 3 providers in parallel via `asyncio.gather()`
- Automatic fallback on provider errors

#### Streaming Service (`streaming_service.py`)

Delivers AI responses token-by-token to Telegram:
1. Collects streamed chunks from AI SDK
2. Every 1 second, calls `message.edit_text()` with accumulated text + cursor `▌`
3. Converts Markdown to Telegram HTML via `formatting.py`
4. On HTML parse error, falls back to plain text
5. If final text > 3800 chars, publishes to Telegraph and shows preview + "Read full" button
6. Adds model signature: `<blockquote>— Model Name | DD.MM.YYYY</blockquote>`

#### Context Service (`context_service.py`)

Manages conversation memory within token limits:
1. Stores every message in `conversations` table
2. Sliding window: keeps last 20 messages in full
3. When window overflows, older messages are summarized by AI into a single paragraph
4. Summary stored in `context_summaries` table and prepended to system prompt
5. User's memory facts are always included in system prompt

#### Memory Service (`memory_service.py`)

Automatically learns about the user:
1. After each AI response, sends a background extraction prompt to detect facts
2. User confirms/rejects each extracted fact
3. Facts categorized: name, preferences, interests, profession, etc.
4. All confirmed facts included in system prompt for all future conversations
5. `/memory` — view, add, delete, manage categories

#### Search Service (`search_service.py`)

Web search integration:
1. Keyword triggers: "найди", "поищи", "что такое", "новости", "сколько стоит", etc.
2. If triggered (or `/search` used), calls Tavily API
3. Search results injected into AI context as additional information
4. AI generates response based on search results + conversation context

#### RAG Service (`rag_service.py`)

Document understanding with vector search:
1. User uploads PDF/DOCX/XLSX/CSV/TXT → text extracted by `file_service.py`
2. Text split into chunks (800 chars, 100 overlap)
3. Each chunk embedded via OpenAI `text-embedding-3-small`
4. Embeddings stored in pgvector column
5. On user query, query is embedded and top-5 similar chunks retrieved
6. Retrieved chunks injected into AI context

#### Voice Service (`voice_service.py` + `tts_pipeline.py`)

Full voice I/O pipeline:

**STT (Speech-to-Text):**
1. Receive Telegram voice message
2. Download OGG file
3. Transcribe via OpenAI Whisper API
4. Send transcription + AI response

**TTS (Text-to-Speech):**
1. Take AI response text
2. **Normalize**: expand numbers (num2words), fix abbreviations
3. **Yofikate**: restore ё where missing (using `yo.dat` dictionary)
4. **Stress marks**: russtress (neural network) + custom overrides database
5. **Pronunciation dict**: apply custom word→pronunciation rules
6. Send to OpenAI gpt-4o-mini-tts with selected voice
7. Return OGG audio to Telegram

#### YouTube Service (`youtube_service.py`)

Full YouTube integration:
- **Video info**: yt-dlp extraction (title, channel, duration, formats)
- **Transcripts**: youtube-transcript-api (multi-language, auto-generated support)
- **Summarization**: For short videos — single AI call. For long videos — chunk transcript into segments, summarize each, then create final summary
- **Download**: yt-dlp with format selection, FFmpeg for audio conversion
- **Progress**: Real-time progress bar via Telegram message edits
- **Large files**: FSInputFile (streaming from disk) for files > 50MB when using Local Bot API
- **File limits**: 50MB (Cloud API) / 2GB (Local Bot API)

#### Image Service (`image_service.py`)

Three image generation providers:
1. **DALL-E 3**: OpenAI API, sizes 1024x1024/1792x1024/1024x1792, styles vivid/natural, quality standard/hd
2. **Gemini Imagen 3**: Google Gemini API image generation
3. **Flux 2 Pro**: Black Forest Labs API

All providers unified behind single interface with inline keyboard controls.

#### Balance Service (`balance_service.py`)

Tracks API spending per service:
- Separate balances for OpenAI, Anthropic, Google AI, Tavily, BFL
- Token-level pricing with per-model rates
- `/balance` shows current spending
- `/setbalance` (admin) resets balances

---

### Quota System

#### Plans

| Plan | Tokens/day | Images/day | YouTube Download | Price |
|------|-----------|-----------|-----------------|-------|
| **free** | 10,000 | 3 | No | — |
| **basic** | 100,000 | 20 | Yes | — |
| **pro** | Unlimited | Unlimited | Yes | — |

#### How It Works

1. **Auto-registration**: On first message, user is created with `free` plan
2. **Token tracking**: After each AI call, actual token count (input + output) is recorded
3. **Image tracking**: After each successful image generation, counter incremented
4. **YouTube gating**: Download buttons check plan before executing
5. **Daily reset**: On each request, if `usage_reset_date < today`, counters atomically reset to 0
6. **In-memory cache**: User objects cached to avoid DB query on every message
7. **Admin control**: `/setplan 123456789 pro` — admin sets any user's plan

#### Database Schema

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(100),
    plan VARCHAR(20) NOT NULL DEFAULT 'free',        -- free / basic / pro
    tokens_used INT NOT NULL DEFAULT 0,
    tokens_limit INT NOT NULL DEFAULT 10000,
    images_used INT NOT NULL DEFAULT 0,
    images_limit INT NOT NULL DEFAULT 3,
    usage_reset_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    expires_at TIMESTAMPTZ
);
CREATE INDEX ix_users_telegram_id ON users(telegram_id);
```

---

### API Costs

#### Per 1M Tokens

| Model | Input | Output |
|-------|-------|--------|
| GPT-5.2 | $1.75 | $14.00 |
| Claude Opus 4.6 | $15.00 | $75.00 |
| Gemini 3 Pro | $1.25 | $10.00 |

#### Per Service

| Service | Price |
|---------|-------|
| Whisper STT | $0.006/min |
| TTS (gpt-4o-mini-tts) | $0.60/1M chars |
| DALL-E 3 (1024x1024) | $0.040/image |
| DALL-E 3 HD (1024x1024) | $0.080/image |
| Gemini Imagen 3 | $0.040/image |
| Flux 2 Pro | $0.050/image |
| Embeddings (text-embedding-3-small) | $0.020/1M tokens |
| Tavily Search | Free tier: 1000 req/month |

---

### Database

PostgreSQL 16 with pgvector extension.

#### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `users` | User accounts & quotas | telegram_id, plan, tokens_used/limit, images_used/limit |
| `conversations` | Chat message history | user_id, role, content, model |
| `context_summaries` | Summarized old context | user_id, summary_text |
| `user_settings` | Per-user preferences | user_id, key, value |
| `bookmarks` | Saved AI responses | user_id, content, note, model |
| `memories` | Facts about users | user_id, category, fact_text |
| `embeddings` | RAG document chunks | user_id, content, embedding (vector) |
| `files` | Uploaded file metadata | user_id, filename, file_type |
| `translator_prompts` | Custom translation prompts | user_id, name, prompt_text |
| `glossary_entries` | Translation glossary | user_id, source, target, embedding |
| `service_balances` | API spending tracker | service_name, balance |
| `pronunciation_rules` | TTS pronunciation dict | word, pronunciation |
| `stress_overrides` | Stress mark corrections | word, stressed_form |

#### Connection

```
Host: 127.0.0.1 (bot uses host network)
Port: 5432
Driver: asyncpg (async)
ORM: SQLAlchemy 2.x (async sessions)
Vector: pgvector extension for embeddings
```

---

### Backups

Automatic daily PostgreSQL backups via cron:

```bash
# Crontab entry (installed automatically)
0 3 * * * /root/multi-ai-bot/scripts/backup_db.sh

# Manual backup
./scripts/backup_db.sh

# Backup location
/media/hdd/ai-bot/backups/

# Format: multi_ai_bot_20260208_030000.sql.gz
# Retention: 7 days (older backups auto-deleted)
```

---

### Troubleshooting

#### Bot doesn't start

```bash
# Check logs
docker logs multi_ai_bot

# Common issues:
# - BOT_TOKEN not set → edit .env
# - DB not ready → wait for PostgreSQL healthcheck
# - Import error → docker compose build --no-cache
```

#### telegram-bot-api doesn't connect

```bash
# Check logs
docker logs telegram_bot_api

# Common issues:
# - "Failed to connect" → XRay proxy not running (systemctl status xray)
# - Wrong API_ID/HASH → check my.telegram.org credentials
# - Timeout → proxychains config wrong (check /etc/proxychains/proxychains.conf in container)

# Verify Local API works
curl --noproxy '*' "http://127.0.0.1:8081/bot<TOKEN>/getMe"
```

#### Google AI API errors (403/429)

```bash
# Google blocks requests from some regions
# Solution: route through US proxy in XRay config
# Check XRay routing:
cat /usr/local/etc/xray/config.json | grep -A5 googleapis

# Gemini 429 fallback chain:
# gemini-3-pro → gemini-2.5-pro → gemini-2.5-flash → gemini-2.0-flash
```

#### pgvector not found

```bash
# Enable extension manually
source .env
PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" \
    -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### Large file upload fails

```bash
# Check if Local Bot API is active
source .env
echo $USE_LOCAL_API  # should be "true"

# Verify Local API responds
curl --noproxy '*' "http://127.0.0.1:8081/bot$BOT_TOKEN/getMe"

# File limits:
# Cloud API: 50MB max
# Local API: 2GB max
```

#### Proxy issues

```bash
# Check XRay is running
systemctl status xray

# Test HTTP proxy
curl -x http://127.0.0.1:10809 https://api.openai.com/v1/models

# Test SOCKS5 proxy
curl -x socks5://127.0.0.1:10808 https://api.openai.com/v1/models

# If bot can't reach APIs, check HTTP_PROXY in docker-compose.yml
```

---

### Roadmap

- [x] ~~Auto-install script for one-click deployment~~ (`install.sh`)
- [x] ~~Multi-user support with separate quotas~~ (plans: free/basic/pro)
- [x] ~~Local Bot API server for large file uploads~~ (2GB via proxychains)
- [ ] Web dashboard for settings and analytics
- [ ] Scheduled messages / reminders
- [ ] Plugin system for custom handlers
- [ ] Group chat support
- [ ] Admin panel in Telegram (inline management)

---

### License

MIT License. See [LICENSE](LICENSE) for details.

---
---

<a id="русский"></a>

## Русский

Продакшн-уровня Telegram-бот, объединяющий **GPT**, **Claude** и **Gemini** в одном интерфейсе с потоковым выводом, голосовым синтезом, генерацией изображений, веб-поиском, RAG-анализом документов, переводом RU↔AR, YouTube-инструментами, мультипользовательскими квотами и локальным Bot API сервером для загрузки файлов до 2ГБ.

> Один бот — все AI-модели, переключение на лету. Полная инфраструктура: прокси-маршрутизация, бэкапы, автоустановщик и управление квотами.

---

### Содержание

- [Возможности](#возможности)
  - [Основной AI](#основной-ai)
  - [Поиск и RAG](#поиск-и-rag)
  - [Голос](#голос)
  - [Перевод (RU ↔ AR)](#перевод-ru--ar)
  - [Генерация изображений](#генерация-изображений)
  - [YouTube](#youtube-1)
  - [Мультипользовательские квоты](#мультипользовательские-квоты)
  - [Утилиты](#утилиты)
- [Архитектура](#архитектура)
  - [Схема системы](#схема-системы)
  - [Ключевые решения](#ключевые-решения)
  - [Docker-сервисы](#docker-сервисы)
  - [Локальный Bot API и Proxychains](#локальный-bot-api-и-proxychains)
  - [Прокси-маршрутизация (XRay/VLESS)](#прокси-маршрутизация-xrayvless)
- [Стек технологий](#стек-технологий)
- [Структура проекта](#структура-проекта)
- [Установка](#установка)
  - [Автоматическая (рекомендуется)](#автоматическая-установка-рекомендуется)
  - [Ручная установка](#ручная-установка)
  - [Настройка прокси](#настройка-прокси-для-заблокированных-регионов)
  - [Настройка локального Bot API](#настройка-локального-bot-api)
- [Конфигурация](#конфигурация)
  - [Переменные окружения](#переменные-окружения)
  - [Модели по умолчанию](#модели-по-умолчанию)
  - [Настройки RAG](#настройки-rag)
  - [Настройки голоса](#настройки-голоса)
- [Команды бота](#команды-бота)
- [Подробно о сервисах](#подробно-о-сервисах)
- [Система квот](#система-квот)
- [Стоимость API](#стоимость-api)
- [База данных](#база-данных)
- [Бэкапы](#бэкапы)
- [Решение проблем](#решение-проблем)
- [Планы развития](#планы-развития)
- [Лицензия](#лицензия)

---

### Возможности

#### Основной AI

| Функция | Описание |
|---------|----------|
| **3 AI-модели** | GPT-5.2, Claude Opus 4.6, Gemini 3 Pro — мгновенное переключение через кнопки или `/model` |
| **Стриминг** | Вывод ответа токен за токеном с анимацией курсора (`▌`), обновление каждую 1 секунду |
| **«Спросить всех»** | Отправить одно сообщение всем 3 моделям одновременно, получить 3 ответа рядом |
| **Умный контекст** | Скользящее окно в 20 сообщений + автоматическая AI-суммаризация старых сообщений |
| **Память** | Бот автоматически запоминает факты о вас (имя, предпочтения, интересы) между сессиями |
| **Сохранение модели** | Выбранная модель сохраняется в PostgreSQL, переживает перезапуски бота |
| **Telegraph** | Ответы длиннее 3800 символов публикуются в Telegraph с кнопкой «Читать полностью» |
| **Подпись** | Каждый ответ подписан: `— Имя модели | дата` в цитате |

#### Поиск и RAG

| Функция | Описание |
|---------|----------|
| **Веб-поиск** | Поиск через Tavily с автоопределением запросов, требующих актуальных данных |
| **Автотриггеры** | Слова «найди», «поищи», «что такое», «новости», «сколько стоит» автоматически запускают поиск |
| **RAG** | Загрузка PDF/DOCX/XLSX/CSV/TXT/изображений → извлечение текста → чанкинг → pgvector-эмбеддинги → семантический поиск |
| **Настройки чанков** | Размер чанка (800), перекрытие (100), top-K (5) — настраивается |
| **OCR** | Отправьте фото → извлечение текста через PyMuPDF + python-docx + openpyxl |

#### Голос

| Функция | Описание |
|---------|----------|
| **Голосовой ввод** | OpenAI Whisper STT — отправьте голосовое, получите расшифровку + ответ AI |
| **TTS** | OpenAI gpt-4o-mini-tts с отдельными голосами: `ash` (GPT), `onyx` (Claude), `echo` (Gemini) |
| **TTS-пайплайн** | Полная цепочка: раскрытие чисел (num2words) → ёфикация → расстановка ударений (russtress + TensorFlow) → словарь произношений |
| **Словарь произношений** | `/pronounce` — добавить/редактировать/удалить произношения слов для TTS |
| **Переопределение ударений** | `/fix` — исправить автоматическую расстановку ударений для конкретных слов |

#### Перевод (RU ↔ AR)

| Функция | Описание |
|---------|----------|
| **Двунаправленный** | Русский → Арабский и Арабский → Русский с автоопределением направления |
| **4 режима ввода** | Текст, голосовые (STT→перевод), фото (OCR→перевод), документы |
| **Сравнение 3 моделей** | Перевести одной моделью, затем мгновенно сравнить все 3 |
| **Исламская терминология** | Специальные промпты для терминологии Акыды и Фикха |
| **Кастомные промпты** | `/translator_prompt` — создавайте и переключайтесь между промптами |
| **Глоссарий** | `/glossary` — пользовательский глоссарий с нечётким поиском через pgvector |
| **Память переводов** | Хранит все переводы, находит похожие сегменты для улучшения согласованности |

#### Генерация изображений

| Функция | Описание |
|---------|----------|
| **3 провайдера** | DALL-E 3, Gemini Imagen 3, Flux 2 Pro (Black Forest Labs) |
| **Управление DALL-E 3** | Размер (1024x1024, 1792x1024, 1024x1792), стиль (vivid/natural), качество (standard/hd) |
| **Inline-управление** | Переключение провайдера, размера, стиля, качества, перегенерация — всё кнопками |
| **Учёт квоты** | Генерация учитывается в дневной квоте пользователя |

#### YouTube

| Функция | Описание |
|---------|----------|
| **Автоопределение** | Отправьте YouTube-ссылку — бот показывает кнопки действий |
| **Инфо о видео** | Название, канал, длительность, просмотры, превью |
| **AI-выжимка** | Извлечение субтитров + AI-суммаризация (для длинных видео — по частям) |
| **Вопросы по видео** | «Спросить о видео» — задавайте вопросы по содержанию |
| **Скачивание видео** | Выбор качества (360p/480p/720p/1080p), прогресс-бар с ETA |
| **Скачивание аудио** | MP3 (128/320 kbps) или WAV, конвертация FFmpeg с прогрессом |
| **Большие файлы** | С Local Bot API: до 2ГБ. Предупреждение при файлах >200МБ |
| **Ограничение** | Скачивание YouTube — только для планов Basic и Pro |

#### Мультипользовательские квоты

| Функция | Описание |
|---------|----------|
| **Авторегистрация** | Пользователь создаётся автоматически при первом сообщении |
| **3 плана** | `free` (10K токенов/день, 3 изображения, без YouTube), `basic` (100K токенов, 20 изображений, YouTube), `pro` (без ограничений) |
| **Ежедневный сброс** | Счётчики обнуляются в полночь (ленивая проверка, без фонового планировщика) |
| **Учёт токенов** | Фактические токены считаются после каждого AI-вызова |
| **`/plan`** | Просмотр текущего плана, использования, лимитов |
| **`/setplan`** | Только для админа: установить план пользователя по Telegram ID |
| **Кэш в памяти** | Данные пользователя кэшируются для экономии запросов к БД |

#### Утилиты

| Функция | Описание |
|---------|----------|
| **Закладки** | Сохраните любой ответ AI, добавьте заметку, ищите по закладкам |
| **Экспорт** | Экспорт диалога в Markdown, JSON или PDF |
| **Трекер расходов** | Отслеживание трат по каждому API-сервису с точностью до токенов |
| **Режим дебатов** | Две AI-модели спорят на выбранную тему |
| **Настройки** | `/settings` — модель по умолчанию, голос, стиль, автопоиск, автопамять |

---

### Архитектура

#### Схема системы

```
┌─────────────────────────────────────────────────────────────────┐
│                         Docker Host                              │
│                                                                  │
│  ┌─────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │ telegram-bot-│    │    Bot (Python)   │    │  PostgreSQL   │  │
│  │ api (Лок.)   │    │  network_mode:    │    │  16 + pgvector│  │
│  │  :8081       │◄───│     host          │───►│  :5432        │  │
│  │  proxychains │    │  HTTP_PROXY ───┐  │    │               │  │
│  │  ──► XRay    │    │               │  │    │  Таблицы:     │  │
│  └──────┬───────┘    └──────────┬────┘  │    │  conversations │  │
│         │                       │       │    │  users         │  │
│         │  MTProto              │       │    │  embeddings    │  │
│         ▼                       ▼       │    │  memories      │  │
│  ┌──────────────┐    ┌──────────────┐   │    │  bookmarks     │  │
│  │  Telegram DC  │    │  XRay/VLESS  │◄──┘    │  ...           │  │
│  │  (через       │    │  :10809 HTTP │        └───────────────┘  │
│  │   прокси ЛВ)  │    │  :10808 SOCKS│                           │
│  └──────────────┘    │              │                            │
│                      │  Исходящие:  │                            │
│                      │  Латвия(осн.)│──► OpenAI, Anthropic       │
│                      │  США (Google)│──► Google AI API            │
│                      └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

#### Ключевые решения

| Решение | Причина |
|---------|---------|
| `network_mode: host` для бота | Доступ к XRay-прокси на `127.0.0.1:10809` без сложностей Docker-сетей |
| `network_mode: host` для telegram-bot-api | proxychains должен достучаться до XRay на localhost |
| Два исходящих в XRay | Латвия (по умолчанию) + США для Google AI API (Google блокирует RU/LV) |
| `proxychains-ng` для Local Bot API | TDLib (MTProto) игнорирует HTTP_PROXY. proxychains перехватывает `connect()` через LD_PRELOAD |
| Ленивый ежедневный сброс | Не нужен фоновый планировщик — квоты сбрасываются при следующем запросе |
| Кэш квот в памяти | Нет запроса к БД на каждое сообщение |
| DI в aiogram | Все сервисы внедряются в Dispatcher, хендлеры получают их параметрами |
| Полностью асинхронный | asyncpg, httpx, aiohttp — никаких блокирующих вызовов |
| Стриминг через edit_text | Интервал 1 секунда — защита от rate limit Telegram (30 ред./мин) |
| pgvector для RAG + глоссария | Одна БД для реляционных данных и векторного поиска |

#### Docker-сервисы

| Сервис | Контейнер | Образ | Сеть | Назначение |
|--------|-----------|-------|------|------------|
| `bot` | `multi_ai_bot` | Кастомный (Python 3.12) | `host` | Основной процесс бота |
| `db` | `multi_ai_bot_db` | `pgvector/pgvector:pg16` | `bridge` (порт 5432) | PostgreSQL + pgvector |
| `telegram-bot-api` | `telegram_bot_api` | Кастомный (proxychains) | `host` | Локальный Telegram Bot API сервер |

#### Локальный Bot API и Proxychains

Локальный Bot API сервер позволяет загружать файлы до **2ГБ** (против 50МБ с Cloud API). Он запускает TDLib-сервер, который общается напрямую с серверами Telegram DC по протоколу MTProto.

**Проблема:** TDLib не поддерживает HTTP_PROXY/HTTPS_PROXY для MTProto-соединений. На серверах, где IP Telegram DC заблокированы (например, Россия), сервер не может подключиться.

**Решение:** Кастомный Docker-образ с `proxychains-ng`:

```
telegram-bot-api/
├── Dockerfile              # На базе aiogram/telegram-bot-api:latest
│                           # + apk add proxychains-ng
│                           # + proxychains.conf → http 127.0.0.1 10809
└── entrypoint-proxy.sh     # exec proxychains4 -q /docker-entrypoint.sh "$@"
```

`proxychains-ng` перехватывает ВСЕ вызовы `connect()` через `LD_PRELOAD`, маршрутизируя каждое TCP-соединение через HTTP-прокси XRay — включая MTProto.

#### Прокси-маршрутизация (XRay/VLESS)

```
Конфиг XRay: /usr/local/etc/xray/config.json

Входящие:
  - HTTP-прокси → 127.0.0.1:10809
  - SOCKS5      → 127.0.0.1:10808

Исходящие (VLESS):
  - Латвия  (62.192.174.164)  ← по умолчанию
  - США     (45.158.127.7)    ← по правилам доменов

Правила маршрутизации:
  - *googleapis.com  → исходящий США (Google блокирует AI API из Латвии/РФ)
  - *google.com      → исходящий США
  - Всё остальное    → исходящий Латвия
```

---

### Стек технологий

| Компонент | Технология | Версия |
|-----------|-----------|--------|
| Фреймворк бота | [aiogram](https://docs.aiogram.dev/) | 3.4+ |
| Язык | Python | 3.12 |
| База данных | PostgreSQL + [pgvector](https://github.com/pgvector/pgvector) | 16 |
| ORM | SQLAlchemy (async) | 2.0+ |
| Миграции | Alembic | 1.13+ |
| AI: GPT | [OpenAI SDK](https://github.com/openai/openai-python) | 1.12+ |
| AI: Claude | [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python) | 0.18+ |
| AI: Gemini | [Google GenAI SDK](https://github.com/googleapis/python-genai) | 1.0+ |
| Поиск | [Tavily API](https://tavily.com/) | 0.5+ |
| Эмбеддинги | OpenAI text-embedding-3-small | — |
| TTS | OpenAI gpt-4o-mini-tts | — |
| STT | OpenAI Whisper | — |
| Ударения | [russtress](https://github.com/Ulitochka/russtress) + TensorFlow/Keras | 0.1.3 |
| Числа→текст | [num2words](https://github.com/savoirfairelinux/num2words) | 0.5.13 |
| Генерация изображений | DALL-E 3, Gemini Imagen 3, [Flux 2 Pro](https://blackforestlabs.ai/) | — |
| YouTube | [yt-dlp](https://github.com/yt-dlp/yt-dlp) + [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) | 2024+ |
| PDF | [PyMuPDF](https://pymupdf.readthedocs.io/) | 1.24+ |
| Документы | [python-docx](https://python-docx.readthedocs.io/) + [openpyxl](https://openpyxl.readthedocs.io/) | — |
| Длинные тексты | [Telegraph API](https://telegra.ph/) | 2.2+ |
| Прокси | [aiohttp-socks](https://github.com/romis2012/aiohttp-socks) + [httpx[socks]](https://www.python-httpx.org/) | — |
| Прокси-туннель | [proxychains-ng](https://github.com/rofl0r/proxychains-ng) | — |
| Контейнеры | Docker + Docker Compose | — |
| VPN/Прокси | XRay/VLESS (два исходящих) | — |
| Локальный Bot API | [telegram-bot-api](https://github.com/tdlib/telegram-bot-api) (образ aiogram) | latest |

---

### Структура проекта

```
multi-ai-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py                    # Точка входа: Dispatcher, DI, регистрация роутеров
│   ├── config.py                  # @dataclass Config с загрузкой из .env
│   ├── database.py                # Async-движок SQLAlchemy + фабрика сессий
│   │
│   ├── handlers/                  # Обработчики сообщений/callback
│   │   ├── __init__.py
│   │   ├── chat.py                # Текст → AI (одна/все модели), перегенерация
│   │   ├── start.py               # /start, /help, /clear, /context, /balance, /plan, /setplan
│   │   ├── model_switch.py        # /model — выбор AI-провайдера
│   │   ├── translator.py          # Режим перевода (RU↔AR), глоссарий, промпты
│   │   ├── voice.py               # Голосовые (STT → AI → опциональный TTS)
│   │   ├── imagegen.py            # /imagine — DALL-E 3 / Imagen / Flux
│   │   ├── youtube.py             # YouTube — инфо, выжимка, скачивание, Q&A
│   │   ├── bookmarks.py           # /bookmarks, сохранение, заметки, экспорт
│   │   ├── files.py               # Загрузка документов → RAG-индексация
│   │   ├── images.py              # OCR фото / Vision API анализ
│   │   ├── search.py              # /search — веб-поиск Tavily
│   │   ├── memory.py              # /memory — управление фактами
│   │   ├── debate.py              # Режим дебатов AI (2 модели)
│   │   └── settings.py            # /settings — настройки пользователя
│   │
│   ├── keyboards/                 # Конструкторы клавиатур
│   │   ├── main_menu.py           # Reply-клавиатура (нижнее меню)
│   │   ├── model_select.py        # Выбор модели + кнопки ответа
│   │   ├── imagegen.py            # Панель управления генерацией
│   │   ├── translator.py          # Клавиатура переводчика
│   │   ├── youtube.py             # Кнопки действий YouTube
│   │   └── settings.py            # Клавиатура настроек
│   │
│   ├── middlewares/
│   │   └── auth.py                # Белый список ADMIN_IDS + авторегистрация
│   │
│   ├── models/                    # ORM-модели SQLAlchemy
│   │   ├── __init__.py            # Все импорты моделей
│   │   ├── user.py                # User: план, квоты, дата сброса
│   │   ├── conversation.py        # История сообщений
│   │   ├── context_summary.py     # Суммаризованный контекст
│   │   ├── user_settings.py       # Настройки пользователя
│   │   ├── bookmark.py            # Сохранённые ответы AI
│   │   ├── memory.py              # Факты о пользователе
│   │   ├── embedding.py           # RAG-эмбеддинги (pgvector)
│   │   ├── file.py                # Метаданные файлов
│   │   ├── translator.py          # Глоссарий + память переводов
│   │   ├── service_balance.py     # Трекер расходов API
│   │   ├── pronunciation_rule.py  # Словарь произношений TTS
│   │   └── stress_override.py     # Переопределения ударений
│   │
│   ├── services/                  # Бизнес-логика
│   │   ├── ai_router.py           # Маршрутизация к GPT/Claude/Gemini
│   │   ├── openai_service.py      # OpenAI: чат, эмбеддинги, DALL-E, Whisper, TTS
│   │   ├── anthropic_service.py   # Claude: messages API, стриминг, vision
│   │   ├── gemini_service.py      # Gemini: generate_content, vision, Imagen
│   │   ├── streaming_service.py   # Потоковый вывод в Telegram + Telegraph
│   │   ├── context_service.py     # Окно контекста + суммаризация
│   │   ├── memory_service.py      # Извлечение фактов + хранение
│   │   ├── quota_service.py       # Квоты по планам (токены, изображения, YouTube)
│   │   ├── search_service.py      # Веб-поиск Tavily
│   │   ├── rag_service.py         # Эмбеддинги + векторный поиск
│   │   ├── translator_service.py  # Логика перевода + глоссарий + TM
│   │   ├── voice_service.py       # Синтез TTS + распознавание STT
│   │   ├── tts_pipeline.py        # Цепочка нормализации для TTS
│   │   ├── image_service.py       # DALL-E 3 / Gemini Imagen / Flux
│   │   ├── youtube_service.py     # yt-dlp + субтитры + скачивание
│   │   ├── bookmark_service.py    # CRUD закладок
│   │   ├── export_service.py      # Экспорт диалогов (MD/JSON/PDF)
│   │   ├── balance_service.py     # Трекер расходов API
│   │   ├── settings_service.py    # CRUD настроек пользователя
│   │   ├── telegraph_service.py   # Длинный текст → Telegraph
│   │   ├── file_service.py        # Хранение файлов + метаданные
│   │   └── debate_service.py      # Оркестрация дебатов AI
│   │
│   ├── utils/
│   │   ├── formatting.py          # Конвертер Markdown → Telegram HTML
│   │   └── prompts.py             # Централизованные системные промпты
│   │
│   └── data/
│       └── yo.dat                 # Словарь ёфикации
│
├── telegram-bot-api/              # Кастомный образ Local Bot API
│   ├── Dockerfile                 # aiogram/telegram-bot-api + proxychains-ng
│   └── entrypoint-proxy.sh        # proxychains4 -q /docker-entrypoint.sh
│
├── alembic/                       # Миграции базы данных
├── prompts/                       # Внешние файлы промптов
│   ├── akida.txt                  # Промпт перевода Акыды
│   └── fiqh.txt                   # Промпт перевода Фикха
│
├── scripts/
│   └── backup_db.sh               # Ежедневный бэкап PostgreSQL (cron)
│
├── docker-compose.yml             # 3 сервиса: bot, db, telegram-bot-api
├── Dockerfile                     # Python 3.12 + ffmpeg + Node.js + yt-dlp
├── requirements.txt               # 23 Python-зависимости
├── install.sh                     # Скрипт автоустановки
├── alembic.ini                    # Конфигурация Alembic
├── .env.example                   # Шаблон переменных окружения
├── .env                           # Локальные секреты (не в git)
├── .gitignore
├── .dockerignore
├── LICENSE                        # Лицензия MIT
└── README.md
```

---

### Установка

#### Автоматическая установка (рекомендуется)

Автоустановщик делает всё: проверка Docker, создание директорий, интерактивная настройка ключей, сборка, проверка запуска.

```bash
git clone https://github.com/Al-Zirr/multi-ai-bot.git
cd multi-ai-bot
chmod +x install.sh
./install.sh
```

Установщик выполнит:
1. Проверку/установку Docker и Docker Compose
2. Создание директорий данных (`/media/hdd/ai-bot/{files,logs,backups,telegram-api,yt-dlp-cache}`)
3. Копирование `.env.example` → `.env` и интерактивный запрос всех API-ключей
4. Автогенерацию надёжного пароля БД
5. Вопрос об использовании Local Bot API (лимит 2ГБ)
6. Запуск `docker compose build` и `docker compose up -d`
7. Ожидание PostgreSQL + проверку запуска бота
8. Активацию расширения pgvector
9. Показ итога: статус контейнеров, настроенные ключи, полезные команды

#### Ручная установка

```bash
# 1. Клонирование
git clone https://github.com/Al-Zirr/multi-ai-bot.git
cd multi-ai-bot

# 2. Конфигурация
cp .env.example .env
nano .env                    # Заполните API-ключи

# 3. Создание директорий
mkdir -p /media/hdd/ai-bot/{files,logs,backups,telegram-api,yt-dlp-cache}

# 4. Сборка и запуск
docker compose up -d --build

# 5. Активация pgvector
source .env
PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" \
    -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 6. Создание таблицы users (если не используете Alembic)
PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" -c "
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(100),
    plan VARCHAR(20) NOT NULL DEFAULT 'free',
    tokens_used INT NOT NULL DEFAULT 0,
    tokens_limit INT NOT NULL DEFAULT 10000,
    images_used INT NOT NULL DEFAULT 0,
    images_limit INT NOT NULL DEFAULT 3,
    usage_reset_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    expires_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_users_telegram_id ON users(telegram_id);
"

# 7. Проверка логов
docker logs -f multi_ai_bot
```

#### Требования

| Требование | Примечание |
|------------|------------|
| Docker + Docker Compose v2 | Автоустановка через `install.sh` |
| Токен Telegram-бота | От [@BotFather](https://t.me/BotFather) |
| Минимум 1 AI API-ключ | OpenAI / Anthropic / Google AI |
| Telegram API ID + Hash | С [my.telegram.org](https://my.telegram.org) (для Local Bot API) |
| (Опционально) Ключ Tavily | Для веб-поиска. Free: 1000 запросов/мес |
| (Опционально) Ключ BFL | Для Flux 2 Pro |
| (Опционально) HTTP/SOCKS-прокси | Для заблокированных регионов (Россия, Иран и др.) |

#### Настройка прокси (для заблокированных регионов)

Если сервер не может напрямую достучаться до AI API (Google блокирует российские IP):

```yaml
# docker-compose.yml — сервис bot
environment:
  HTTP_PROXY: http://127.0.0.1:10809
  HTTPS_PROXY: http://127.0.0.1:10809
```

Бот в `network_mode: host` — видит все localhost-сервисы хоста.

Для **двойной маршрутизации** (разные прокси для разных AI-провайдеров):

```json
// Пример правила маршрутизации XRay
{
  "type": "field",
  "domain": ["googleapis.com", "google.com"],
  "outboundTag": "usa-outbound"
}
```

#### Настройка локального Bot API

Локальный Bot API позволяет загружать файлы до **2ГБ** (против 50МБ с Cloud API).

1. Установите в `.env`:
```bash
USE_LOCAL_API=true
LOCAL_API_URL=http://127.0.0.1:8081
TELEGRAM_API_ID=ваш_api_id       # с my.telegram.org
TELEGRAM_API_HASH=ваш_api_hash   # с my.telegram.org
```

2. Сервис `telegram-bot-api` уже настроен в `docker-compose.yml`. Он собирает кастомный образ с `proxychains-ng`, который туннелирует MTProto через ваш прокси.

3. Перезапуск:
```bash
docker compose up -d --build telegram-bot-api
```

4. Проверка:
```bash
curl --noproxy '*' "http://127.0.0.1:8081/bot<ВАШ_ТОКЕН>/getMe"
# Должно вернуть {"ok":true,"result":{...}}
```

---

### Конфигурация

#### Переменные окружения

Все настройки в `.env`. Полный справочник:

```bash
# ═══════════════ Telegram ═══════════════
BOT_TOKEN=                    # Токен бота от @BotFather
TELEGRAM_API_ID=              # api_id с my.telegram.org
TELEGRAM_API_HASH=            # api_hash с my.telegram.org
ADMIN_IDS=                    # Telegram ID через запятую
USE_LOCAL_API=false            # true = Local Bot API, false = Cloud API
LOCAL_API_URL=http://127.0.0.1:8081

# ═══════════════ AI-модели ═══════════════
OPENAI_API_KEY=               # GPT, TTS, STT, DALL-E, эмбеддинги
ANTHROPIC_API_KEY=            # Claude
GOOGLE_AI_API_KEY=            # Gemini

# ═══════════════ Модели по умолчанию ═══════════════
DEFAULT_GPT_MODEL=gpt-5.2
DEFAULT_CLAUDE_MODEL=claude-opus-4-6
DEFAULT_GEMINI_MODEL=gemini-3-pro-preview
DEFAULT_MODEL=claude           # Провайдер: gpt / claude / gemini

# ═══════════════ База данных ═══════════════
DB_HOST=127.0.0.1
DB_PORT=5432
DB_USER=multi_ai_bot
DB_PASSWORD=                   # Надёжный пароль (генерируется install.sh)
DB_NAME=multi_ai_bot

# ═══════════════ Стриминг ═══════════════
STREAMING_ENABLED=true
STREAMING_UPDATE_INTERVAL=1.0  # Секунды между обновлениями сообщений

# ═══════════════ Контекст ═══════════════
MAX_CONTEXT_MESSAGES=20        # Сообщений до начала суммаризации

# ═══════════════ Поиск ═══════════════
TAVILY_API_KEY=                # Ключ Tavily для веб-поиска
AUTO_SEARCH=true               # Автоопределение поисковых запросов

# ═══════════════ RAG / Эмбеддинги ═══════════════
EMBEDDING_MODEL=text-embedding-3-small
RAG_CHUNK_SIZE=800
RAG_CHUNK_OVERLAP=100
RAG_TOP_K=5

# ═══════════════ Голос ═══════════════
TTS_VOICE_GPT=ash              # Голос для GPT
TTS_VOICE_CLAUDE=onyx          # Голос для Claude
TTS_VOICE_GEMINI=echo          # Голос для Gemini

# ═══════════════ Генерация изображений ═══════════════
BFL_API_KEY=                   # Black Forest Labs (Flux 2 Pro)

# ═══════════════ Файлы ═══════════════
FILES_DIR=/app/files           # Внутри контейнера
```

#### Модели по умолчанию

| Переменная | Значение | Описание |
|------------|----------|----------|
| `DEFAULT_GPT_MODEL` | `gpt-5.2` | Модель OpenAI |
| `DEFAULT_CLAUDE_MODEL` | `claude-opus-4-6` | Модель Anthropic |
| `DEFAULT_GEMINI_MODEL` | `gemini-3-pro-preview` | Модель Google |
| `DEFAULT_MODEL` | `claude` | Провайдер по умолчанию для новых пользователей |

#### Настройки RAG

| Переменная | Значение | Описание |
|------------|----------|----------|
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Модель эмбеддингов |
| `RAG_CHUNK_SIZE` | `800` | Символов в одном чанке документа |
| `RAG_CHUNK_OVERLAP` | `100` | Перекрытие между соседними чанками |
| `RAG_TOP_K` | `5` | Количество релевантных чанков для поиска |

#### Настройки голоса

| Переменная | Значение | Описание |
|------------|----------|----------|
| `TTS_VOICE_GPT` | `ash` | Голос для GPT |
| `TTS_VOICE_CLAUDE` | `onyx` | Голос для Claude |
| `TTS_VOICE_GEMINI` | `echo` | Голос для Gemini |

Доступные голоса: `alloy`, `ash`, `ballad`, `coral`, `echo`, `fable`, `nova`, `onyx`, `sage`, `shimmer`

---

### Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Запуск бота, приветственное сообщение |
| `/help` | Показать все команды |
| `/model` | Переключить AI-модель (GPT / Claude / Gemini / Все) |
| `/search [запрос]` | Веб-поиск через Tavily |
| `/imagine [промпт]` | Генерация изображений (DALL-E 3 / Imagen / Flux) |
| `/memory` | Просмотр и управление фактами о вас |
| `/bookmarks` | Просмотр сохранённых ответов AI |
| `/export` | Экспорт диалога (Markdown / JSON / PDF) |
| `/balance` | Проверка расходов по сервисам |
| `/plan` | Просмотр плана, использования, лимитов |
| `/setplan [user_id] [план]` | Админ: установить план (free/basic/pro) |
| `/setbalance [сервис] [сумма]` | Админ: установить баланс |
| `/pronounce` | Управление словарём произношений TTS |
| `/fix` | Управление переопределениями ударений |
| `/glossary` | Управление терминами глоссария переводчика |
| `/translator_prompt` | Управление промптами переводчика |
| `/context` | Статистика окна контекста |
| `/settings` | Настройки пользователя |
| `/clear` | Очистить историю диалога |

**Inline-кнопки под каждым ответом AI:**

| Кнопка | Действие |
|--------|----------|
| Перегенерировать (🔄) | Отправить тот же промпт для другого ответа |
| GPT / Claude / Gemini | Переспросить другую модель |
| Все модели | Получить ответы от всех 3 моделей |
| Озвучить (🔊) | Озвучить ответ |
| Закладка (🔖) | Сохранить ответ |

**Reply-клавиатура (нижнее меню):**

| Кнопка | Действие |
|--------|----------|
| Модель | Быстрое переключение модели |
| Переводчик | Вход/выход из режима перевода |
| Генерация | Быстрый доступ к `/imagine` |
| Баланс | Быстрый доступ к `/balance` |
| Контекст | Быстрый доступ к `/context` |
| Очистить | Быстрый доступ к `/clear` |

---

### Подробно о сервисах

#### AI-маршрутизатор (`ai_router.py`)

Центральный диспетчер, направляющий сообщения к активному AI-провайдеру. Управляет экземплярами `OpenAIService`, `AnthropicService` и `GeminiService`. Поддерживает:
- Выбор модели для каждого пользователя (сохраняется в БД)
- Режим «Спросить всех» — отправляет всем 3 провайдерам параллельно через `asyncio.gather()`
- Автоматический фоллбэк при ошибках провайдера

#### Стриминг (`streaming_service.py`)

Доставляет ответы AI токен за токеном в Telegram:
1. Собирает стримовые чанки из AI SDK
2. Каждую 1 секунду вызывает `message.edit_text()` с накопленным текстом + курсор `▌`
3. Конвертирует Markdown в Telegram HTML через `formatting.py`
4. При ошибке HTML-парсинга откатывается на простой текст
5. Если итоговый текст > 3800 символов — публикует в Telegraph с кнопкой «Читать полностью»
6. Добавляет подпись: `<blockquote>— Имя модели | ДД.ММ.ГГГГ</blockquote>`

#### Контекст (`context_service.py`)

Управляет памятью диалога в рамках лимитов токенов:
1. Сохраняет каждое сообщение в таблицу `conversations`
2. Скользящее окно: хранит последние 20 сообщений полностью
3. При переполнении старые сообщения суммаризируются AI в один абзац
4. Суммария хранится в `context_summaries` и добавляется в системный промпт
5. Факты из памяти пользователя всегда включены в системный промпт

#### Память (`memory_service.py`)

Автоматически учится о пользователе:
1. После каждого ответа AI отправляет фоновый запрос на извлечение фактов
2. Пользователь подтверждает/отклоняет каждый извлечённый факт
3. Факты категоризируются: имя, предпочтения, интересы, профессия и др.
4. Все подтверждённые факты включаются в системный промпт навсегда
5. `/memory` — просмотр, добавление, удаление, управление категориями

#### YouTube (`youtube_service.py`)

Полная интеграция YouTube:
- **Инфо о видео**: извлечение через yt-dlp (название, канал, длительность, форматы)
- **Субтитры**: youtube-transcript-api (мультиязычные, автогенерированные)
- **Суммаризация**: Для коротких видео — один AI-вызов. Для длинных — чанкинг субтитров, суммаризация каждого, итоговая сводка
- **Скачивание**: yt-dlp с выбором формата, FFmpeg для аудио
- **Прогресс**: Прогресс-бар в реальном времени через редактирование сообщений
- **Большие файлы**: FSInputFile (стриминг с диска) для файлов > 50МБ при Local Bot API
- **Лимиты файлов**: 50МБ (Cloud API) / 2ГБ (Local Bot API)

#### Голос (`voice_service.py` + `tts_pipeline.py`)

**STT (Речь→Текст):**
1. Получение голосового сообщения Telegram
2. Скачивание OGG-файла
3. Транскрипция через OpenAI Whisper API
4. Отправка расшифровки + ответ AI

**TTS (Текст→Речь):**
1. Текст ответа AI
2. **Нормализация**: раскрытие чисел (num2words), исправление сокращений
3. **Ёфикация**: восстановление ё (словарь `yo.dat`)
4. **Ударения**: russtress (нейросеть) + пользовательские переопределения
5. **Словарь произношений**: применение пользовательских правил
6. Отправка в OpenAI gpt-4o-mini-tts с выбранным голосом
7. Возврат OGG-аудио в Telegram

---

### Система квот

#### Планы

| План | Токены/день | Изображения/день | Скачивание YouTube | Стоимость |
|------|-------------|-------------------|-------------------|-----------|
| **free** | 10 000 | 3 | Нет | — |
| **basic** | 100 000 | 20 | Да | — |
| **pro** | Без ограничений | Без ограничений | Да | — |

#### Как это работает

1. **Авторегистрация**: При первом сообщении пользователь создаётся с планом `free`
2. **Учёт токенов**: После каждого AI-вызова записывается фактическое количество токенов
3. **Учёт изображений**: Счётчик +1 после каждой успешной генерации
4. **YouTube**: Кнопки скачивания проверяют план перед выполнением
5. **Ежедневный сброс**: При каждом запросе, если `usage_reset_date < today`, счётчики атомарно обнуляются
6. **Кэш**: Объекты пользователя в памяти — нет запроса к БД на каждое сообщение
7. **Админ**: `/setplan 123456789 pro` — установить план любому пользователю

#### Схема таблицы

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(100),
    plan VARCHAR(20) NOT NULL DEFAULT 'free',        -- free / basic / pro
    tokens_used INT NOT NULL DEFAULT 0,
    tokens_limit INT NOT NULL DEFAULT 10000,
    images_used INT NOT NULL DEFAULT 0,
    images_limit INT NOT NULL DEFAULT 3,
    usage_reset_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    expires_at TIMESTAMPTZ
);
CREATE INDEX ix_users_telegram_id ON users(telegram_id);
```

---

### Стоимость API

#### За 1M токенов

| Модель | Вход | Выход |
|--------|------|-------|
| GPT-5.2 | $1.75 | $14.00 |
| Claude Opus 4.6 | $15.00 | $75.00 |
| Gemini 3 Pro | $1.25 | $10.00 |

#### За сервис

| Сервис | Цена |
|--------|------|
| Whisper STT | $0.006/мин |
| TTS (gpt-4o-mini-tts) | $0.60/1M символов |
| DALL-E 3 (1024x1024) | $0.040/изображение |
| DALL-E 3 HD (1024x1024) | $0.080/изображение |
| Gemini Imagen 3 | $0.040/изображение |
| Flux 2 Pro | $0.050/изображение |
| Эмбеддинги (text-embedding-3-small) | $0.020/1M токенов |
| Поиск Tavily | Бесплатно: 1000 запросов/мес |

---

### База данных

PostgreSQL 16 с расширением pgvector.

#### Таблицы

| Таблица | Назначение | Ключевые столбцы |
|---------|------------|------------------|
| `users` | Аккаунты и квоты | telegram_id, plan, tokens_used/limit, images_used/limit |
| `conversations` | История сообщений | user_id, role, content, model |
| `context_summaries` | Суммаризованный контекст | user_id, summary_text |
| `user_settings` | Настройки пользователя | user_id, key, value |
| `bookmarks` | Сохранённые ответы | user_id, content, note, model |
| `memories` | Факты о пользователях | user_id, category, fact_text |
| `embeddings` | RAG-чанки документов | user_id, content, embedding (vector) |
| `files` | Метаданные файлов | user_id, filename, file_type |
| `translator_prompts` | Промпты перевода | user_id, name, prompt_text |
| `glossary_entries` | Глоссарий переводчика | user_id, source, target, embedding |
| `service_balances` | Трекер расходов | service_name, balance |
| `pronunciation_rules` | Словарь произношений | word, pronunciation |
| `stress_overrides` | Переопределения ударений | word, stressed_form |

#### Подключение

```
Хост: 127.0.0.1 (бот в сети хоста)
Порт: 5432
Драйвер: asyncpg (async)
ORM: SQLAlchemy 2.x (async-сессии)
Вектор: расширение pgvector для эмбеддингов
```

---

### Бэкапы

Автоматический ежедневный бэкап PostgreSQL через cron:

```bash
# Запись в crontab
0 3 * * * /root/multi-ai-bot/scripts/backup_db.sh

# Ручной бэкап
./scripts/backup_db.sh

# Директория бэкапов
/media/hdd/ai-bot/backups/

# Формат: multi_ai_bot_20260208_030000.sql.gz
# Хранение: 7 дней (старые удаляются автоматически)
```

---

### Решение проблем

#### Бот не запускается

```bash
# Проверьте логи
docker logs multi_ai_bot

# Частые проблемы:
# - BOT_TOKEN не задан → отредактируйте .env
# - БД не готова → дождитесь healthcheck PostgreSQL
# - Ошибка импорта → docker compose build --no-cache
```

#### telegram-bot-api не подключается

```bash
# Проверьте логи
docker logs telegram_bot_api

# Частые проблемы:
# - "Failed to connect" → XRay не запущен (systemctl status xray)
# - Неверный API_ID/HASH → проверьте данные my.telegram.org
# - Таймаут → неправильный конфиг proxychains

# Проверка работы Local API
curl --noproxy '*' "http://127.0.0.1:8081/bot<ТОКЕН>/getMe"
```

#### Ошибки Google AI API (403/429)

```bash
# Google блокирует запросы из некоторых регионов
# Решение: маршрутизация через US-прокси в XRay
# Проверьте маршрутизацию:
cat /usr/local/etc/xray/config.json | grep -A5 googleapis

# Фоллбэк-цепочка Gemini при 429:
# gemini-3-pro → gemini-2.5-pro → gemini-2.5-flash → gemini-2.0-flash
```

#### pgvector не найден

```bash
source .env
PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" \
    -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### Большой файл не загружается

```bash
# Проверьте, активен ли Local Bot API
source .env
echo $USE_LOCAL_API  # должно быть "true"

# Проверьте ответ Local API
curl --noproxy '*' "http://127.0.0.1:8081/bot$BOT_TOKEN/getMe"

# Лимиты файлов:
# Cloud API: максимум 50МБ
# Local API: максимум 2ГБ
```

#### Проблемы с прокси

```bash
# Проверьте XRay
systemctl status xray

# Тест HTTP-прокси
curl -x http://127.0.0.1:10809 https://api.openai.com/v1/models

# Тест SOCKS5
curl -x socks5://127.0.0.1:10808 https://api.openai.com/v1/models
```

---

### Планы развития

- [x] ~~Скрипт автоустановки~~ (`install.sh`)
- [x] ~~Мультипользовательский режим с квотами~~ (планы: free/basic/pro)
- [x] ~~Локальный Bot API для больших файлов~~ (2ГБ через proxychains)
- [ ] Веб-панель для настроек и аналитики
- [ ] Отложенные сообщения / напоминания
- [ ] Система плагинов для кастомных обработчиков
- [ ] Поддержка групповых чатов
- [ ] Админ-панель в Telegram (inline-управление)

---

### Лицензия

Лицензия MIT. Подробнее в файле [LICENSE](LICENSE).
