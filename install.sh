#!/bin/bash
# ══════════════════════════════════════════════════════════
#  Multi-AI Bot — Installer
#  Автоматическая установка и настройка
# ══════════════════════════════════════════════════════════

set -euo pipefail

# ─── Colors ───────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ─── Helpers ──────────────────────────────────────────────
info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()      { echo -e "${GREEN}[  OK]${NC}  $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
fail()    { echo -e "${RED}[FAIL]${NC}  $1"; }
step()    { echo -e "\n${BOLD}${CYAN}══ $1 ══${NC}"; }
ask()     { echo -en "${YELLOW}  → $1: ${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ══════════════════════════════════════════════════════════
#  Banner
# ══════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${CYAN}"
echo "  __  __       _ _   _        _    ___   ____        _   "
echo " |  \/  |_   _| | |_(_)      / \  |_ _| | __ )  ___ | |_ "
echo " | |\/| | | | | | __| |____ / _ \  | |  |  _ \ / _ \| __|"
echo " | |  | | |_| | | |_| |____/ ___ \ | |  | |_) | (_) | |_ "
echo " |_|  |_|\__,_|_|\__|_|   /_/   \_\___| |____/ \___/ \__|"
echo -e "${NC}"
echo -e "${DIM}  GPT + Claude + Gemini | Streaming | TTS | RAG | YouTube${NC}"
echo ""

# ══════════════════════════════════════════════════════════
#  1. Docker check
# ══════════════════════════════════════════════════════════
step "1/6  Docker"

if command -v docker &>/dev/null; then
    DOCKER_VER=$(docker --version | grep -oP '\d+\.\d+\.\d+' | head -1)
    ok "Docker $DOCKER_VER"
else
    warn "Docker не установлен. Устанавливаю..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
    ok "Docker установлен"
fi

if docker compose version &>/dev/null; then
    COMPOSE_VER=$(docker compose version --short 2>/dev/null || echo "v2+")
    ok "Docker Compose $COMPOSE_VER"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_VER=$(docker-compose --version | grep -oP '\d+\.\d+\.\d+' | head -1)
    ok "docker-compose $COMPOSE_VER (standalone)"
    warn "Рекомендуется Docker Compose V2 (plugin)"
else
    warn "Docker Compose не установлен. Устанавливаю plugin..."
    apt-get update -qq && apt-get install -y -qq docker-compose-plugin
    ok "Docker Compose plugin установлен"
fi

# ══════════════════════════════════════════════════════════
#  2. Directories
# ══════════════════════════════════════════════════════════
step "2/6  Директории"

DIRS=(
    "/media/hdd/ai-bot/files"
    "/media/hdd/ai-bot/logs"
    "/media/hdd/ai-bot/backups"
    "/media/hdd/ai-bot/telegram-api"
    "/media/hdd/ai-bot/yt-dlp-cache"
)

for dir in "${DIRS[@]}"; do
    if [ -d "$dir" ]; then
        ok "$dir"
    else
        mkdir -p "$dir"
        ok "$dir  ${DIM}(создана)${NC}"
    fi
done

# ══════════════════════════════════════════════════════════
#  3. .env configuration
# ══════════════════════════════════════════════════════════
step "3/6  Конфигурация .env"

if [ -f .env ]; then
    info ".env уже существует"
    echo ""
    echo -en "${YELLOW}  Перезаписать? (y/N): ${NC}"
    read -r OVERWRITE
    if [[ "$OVERWRITE" != "y" && "$OVERWRITE" != "Y" ]]; then
        ok "Оставляю текущий .env"
        SKIP_ENV=true
    else
        cp .env ".env.backup.$(date +%Y%m%d_%H%M%S)"
        ok "Бэкап сохранён"
        SKIP_ENV=false
    fi
else
    SKIP_ENV=false
fi

if [ "$SKIP_ENV" = false ]; then
    cp .env.example .env
    info "Заполните API ключи (Enter = пропустить)"
    echo ""

    # ── Helper: set value in .env ──
    set_env() {
        local key="$1" val="$2"
        if [ -n "$val" ]; then
            # Escape special chars for sed
            local escaped_val
            escaped_val=$(printf '%s\n' "$val" | sed 's/[&/\]/\\&/g')
            sed -i "s|^${key}=.*|${key}=${escaped_val}|" .env
        fi
    }

    # ── Telegram ──
    echo -e "  ${BOLD}Telegram${NC}"

    ask "BOT_TOKEN (от @BotFather)"
    read -r VAL; set_env "BOT_TOKEN" "$VAL"

    ask "TELEGRAM_API_ID (my.telegram.org)"
    read -r VAL; set_env "TELEGRAM_API_ID" "$VAL"

    ask "TELEGRAM_API_HASH (my.telegram.org)"
    read -r VAL; set_env "TELEGRAM_API_HASH" "$VAL"

    ask "ADMIN_IDS (Telegram ID, через запятую)"
    read -r VAL; set_env "ADMIN_IDS" "$VAL"

    echo ""
    echo -e "  ${BOLD}AI Models${NC}"

    ask "OPENAI_API_KEY"
    read -r VAL; set_env "OPENAI_API_KEY" "$VAL"

    ask "ANTHROPIC_API_KEY"
    read -r VAL; set_env "ANTHROPIC_API_KEY" "$VAL"

    ask "GOOGLE_AI_API_KEY"
    read -r VAL; set_env "GOOGLE_AI_API_KEY" "$VAL"

    echo ""
    echo -e "  ${BOLD}Database${NC}"

    # Generate random password if not provided
    DEFAULT_PASS=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 20)
    ask "DB_PASSWORD (Enter = сгенерировать)"
    read -r VAL
    if [ -z "$VAL" ]; then
        VAL="$DEFAULT_PASS"
        info "Сгенерирован: $VAL"
    fi
    set_env "DB_PASSWORD" "$VAL"

    echo ""
    echo -e "  ${BOLD}Дополнительно${NC} ${DIM}(можно пропустить)${NC}"

    ask "TAVILY_API_KEY (веб-поиск)"
    read -r VAL; set_env "TAVILY_API_KEY" "$VAL"

    ask "BFL_API_KEY (Flux изображения)"
    read -r VAL; set_env "BFL_API_KEY" "$VAL"

    echo ""
    echo -e "  ${BOLD}Local Bot API${NC}"
    echo -en "${YELLOW}  → Использовать локальный Telegram API? (y/N): ${NC}"
    read -r USE_LOCAL
    if [[ "$USE_LOCAL" == "y" || "$USE_LOCAL" == "Y" ]]; then
        set_env "USE_LOCAL_API" "true"
        ok "Local Bot API включён (лимит файлов 2GB)"
    else
        set_env "USE_LOCAL_API" "false"
        ok "Cloud API (лимит файлов 50MB)"
    fi

    echo ""
    ok ".env настроен"
fi

# ══════════════════════════════════════════════════════════
#  4. Build & Start
# ══════════════════════════════════════════════════════════
step "4/6  Сборка и запуск"

info "docker compose build..."
docker compose build --quiet 2>&1 | tail -5
ok "Образы собраны"

info "docker compose up -d..."
docker compose up -d 2>&1
ok "Контейнеры запущены"

# ══════════════════════════════════════════════════════════
#  5. Wait for startup
# ══════════════════════════════════════════════════════════
step "5/6  Проверка запуска"

# Wait for DB
info "Жду PostgreSQL..."
for i in $(seq 1 30); do
    if docker exec multi_ai_bot_db pg_isready -U multi_ai_bot &>/dev/null; then
        ok "PostgreSQL готов"
        break
    fi
    if [ "$i" -eq 30 ]; then
        fail "PostgreSQL не запустился за 30 секунд"
        docker logs multi_ai_bot_db 2>&1 | tail -5
        exit 1
    fi
    sleep 1
done

# Enable pgvector extension
source .env
PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" \
    -c "CREATE EXTENSION IF NOT EXISTS vector;" &>/dev/null && \
    ok "pgvector extension" || warn "pgvector extension (может уже существовать)"

# Wait for bot
info "Жду бот..."
BOT_OK=false
for i in $(seq 1 30); do
    if docker logs multi_ai_bot 2>&1 | grep -q "Start polling" ; then
        ok "Бот запущен и polling"
        BOT_OK=true
        break
    fi
    if docker logs multi_ai_bot 2>&1 | grep -qE "Error|Traceback" ; then
        # Check if it recovered
        if docker logs multi_ai_bot 2>&1 | tail -5 | grep -q "Start polling"; then
            ok "Бот запущен (после переподключения)"
            BOT_OK=true
            break
        fi
    fi
    sleep 2
done

if [ "$BOT_OK" = false ]; then
    fail "Бот не запустился за 60 секунд"
    echo -e "${DIM}"
    docker logs multi_ai_bot 2>&1 | tail -15
    echo -e "${NC}"
    echo -e "${YELLOW}  Проверьте логи: docker logs multi_ai_bot${NC}"
fi

# Check telegram-bot-api if local
source .env
if [ "${USE_LOCAL_API:-false}" = "true" ]; then
    info "Проверяю Local Bot API..."
    LOCAL_OK=false
    for i in $(seq 1 15); do
        RESP=$(timeout 5 curl -s --noproxy '*' "http://127.0.0.1:8081/bot$BOT_TOKEN/getMe" 2>/dev/null || true)
        if echo "$RESP" | grep -q '"ok":true'; then
            ok "Local Bot API работает"
            LOCAL_OK=true
            break
        fi
        sleep 2
    done
    if [ "$LOCAL_OK" = false ]; then
        warn "Local Bot API не отвечает (MTProto через proxy может быть медленным)"
        info "Проверьте: docker logs telegram_bot_api"
    fi
fi

# ══════════════════════════════════════════════════════════
#  6. Summary
# ══════════════════════════════════════════════════════════
step "6/6  Итог"

echo ""
echo -e "${BOLD}  Контейнеры:${NC}"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null | while IFS= read -r line; do
    if echo "$line" | grep -qi "up\|running"; then
        echo -e "    ${GREEN}●${NC} $line"
    elif echo "$line" | grep -qi "name"; then
        echo -e "    $line"
    else
        echo -e "    ${RED}●${NC} $line"
    fi
done

echo ""

# Check which keys are configured
source .env
echo -e "${BOLD}  API ключи:${NC}"
[ -n "${BOT_TOKEN:-}" ]         && echo -e "    ${GREEN}●${NC} Telegram Bot Token" || echo -e "    ${RED}●${NC} Telegram Bot Token — ${RED}не задан!${NC}"
[ -n "${OPENAI_API_KEY:-}" ]    && echo -e "    ${GREEN}●${NC} OpenAI (GPT, TTS)" || echo -e "    ${YELLOW}●${NC} OpenAI — не задан"
[ -n "${ANTHROPIC_API_KEY:-}" ] && echo -e "    ${GREEN}●${NC} Anthropic (Claude)" || echo -e "    ${YELLOW}●${NC} Anthropic — не задан"
[ -n "${GOOGLE_AI_API_KEY:-}" ] && echo -e "    ${GREEN}●${NC} Google AI (Gemini)" || echo -e "    ${YELLOW}●${NC} Google AI — не задан"
[ -n "${TAVILY_API_KEY:-}" ]    && echo -e "    ${GREEN}●${NC} Tavily (поиск)" || echo -e "    ${DIM}●${NC} Tavily — не задан ${DIM}(опционально)${NC}"
[ -n "${BFL_API_KEY:-}" ]       && echo -e "    ${GREEN}●${NC} BFL (Flux изображения)" || echo -e "    ${DIM}●${NC} BFL — не задан ${DIM}(опционально)${NC}"

echo ""
echo -e "${BOLD}  Режим API:${NC}"
if [ "${USE_LOCAL_API:-false}" = "true" ]; then
    echo -e "    ${GREEN}●${NC} Local Bot API (лимит файлов: 2GB)"
else
    echo -e "    ${BLUE}●${NC} Cloud API (лимит файлов: 50MB)"
fi

echo ""
echo -e "${BOLD}  Полезные команды:${NC}"
echo -e "    ${DIM}docker compose logs -f bot${NC}      — логи бота"
echo -e "    ${DIM}docker compose restart bot${NC}      — перезапуск бота"
echo -e "    ${DIM}docker compose down${NC}             — остановка"
echo -e "    ${DIM}docker compose up -d --build${NC}    — пересборка"
echo -e "    ${DIM}nano .env${NC}                       — редактировать конфиг"

echo ""

# Final check
if [ -z "${BOT_TOKEN:-}" ]; then
    echo -e "${RED}${BOLD}  ! BOT_TOKEN не задан — бот не сможет работать${NC}"
    echo -e "${YELLOW}    Отредактируйте .env и перезапустите: docker compose restart bot${NC}"
elif [ -z "${OPENAI_API_KEY:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -z "${GOOGLE_AI_API_KEY:-}" ]; then
    echo -e "${YELLOW}${BOLD}  ! Ни один AI ключ не задан${NC}"
    echo -e "${YELLOW}    Добавьте хотя бы один ключ в .env${NC}"
else
    BOT_NAME=$(docker logs multi_ai_bot 2>&1 | grep -oP '@\w+' | tail -1 || echo "")
    if [ -n "$BOT_NAME" ]; then
        echo -e "${GREEN}${BOLD}  Бот готов к работе!${NC}  Telegram: ${BOLD}${BOT_NAME}${NC}"
    else
        echo -e "${GREEN}${BOLD}  Бот готов к работе!${NC}"
    fi
fi

echo ""
