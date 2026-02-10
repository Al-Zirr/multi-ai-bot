"""YouTube handler: summarize, download video/audio."""

import logging
import os

from aiogram import Router, F
from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery, BufferedInputFile, FSInputFile

from bot.keyboards.youtube import (
    get_youtube_menu,
    get_video_quality_keyboard,
    get_audio_format_keyboard,
    get_summary_keyboard,
)
from bot.services.ai_router import AIRouter
from bot.services.balance_service import BalanceService
from bot.services.settings_service import SettingsService
from bot.services.youtube_service import (
    YouTubeService,
    MAX_FILE_SIZE_CLOUD,
    LARGE_FILE_WARNING,
    format_duration,
)
from bot.services.quota_service import QuotaService
from bot.utils.formatting import md_to_html
from bot.utils.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)
router = Router()

# Per-user state
_yt_state: dict[int, dict] = {}

SUMMARY_PROMPT = (
    "Сделай краткую выжимку этого видео на основе субтитров.\n"
    "Раздели по основным темам/разделам с таймкодами [HH:MM:SS].\n\n"
    "Формат:\n"
    "Основная мысль: ...\n\n"
    "Темы:\n"
    "[00:00:00] Тема 1 — краткое описание\n"
    "[00:05:30] Тема 2 — краткое описание\n"
    "...\n\n"
    "Ключевые тезисы:\n"
    "- ...\n"
    "- ...\n"
)

CHUNK_SUMMARY_PROMPT = (
    "Сделай краткую выжимку этой части видео на основе субтитров.\n"
    "Укажи основные темы с таймкодами [HH:MM:SS].\n"
)

MERGE_SUMMARY_PROMPT = (
    "Ниже — суммаризации частей длинного видео.\n"
    "Объедини их в одну связную выжимку.\n"
    "Формат:\n"
    "Основная мысль: ...\n\n"
    "Темы:\n"
    "[HH:MM:SS] Тема — описание\n"
    "...\n\n"
    "Ключевые тезисы:\n"
    "- ...\n"
)

# 30-minute chunks for long videos (in seconds)
CHUNK_DURATION = 30 * 60
# Max transcript length per AI call (~15000 tokens ≈ 60000 chars)
MAX_TRANSCRIPT_CHARS = 60000


def _make_progress_callback(waiting_msg, label: str):
    """Create async callback for yt-dlp progress updates."""

    async def update(downloaded: int, total: int):
        if total == 0:
            text = f"{label}\n\u041a\u043e\u043d\u0432\u0435\u0440\u0442\u0430\u0446\u0438\u044f..."
        else:
            pct = downloaded / total * 100
            filled = int(pct / 100 * 16)
            bar = "\u2588" * filled + "\u2591" * (16 - filled)
            dl_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            text = f"{label}\n[{bar}] {pct:.0f}% | {dl_mb:.1f} / {total_mb:.1f} MB"
        try:
            await waiting_msg.edit_text(text)
        except Exception:
            pass

    return update


class YouTubeURL(Filter):
    """Filter: matches messages containing YouTube URLs."""

    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
        return YouTubeService.extract_video_id(message.text) is not None


class YouTubeAskMode(Filter):
    """Filter: user is in 'ask about video' mode."""

    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
        state = _yt_state.get(message.from_user.id)
        return state is not None and state.get("ask_mode", False)


# ═══════════════════════════════════════════════════════
#  ASK MODE (must be before YouTubeURL to catch plain text)
# ═══════════════════════════════════════════════════════

@router.message(YouTubeAskMode(), F.text)
async def handle_ask_about_video(
    message: Message,
    ai_router: AIRouter,
    balance_service: BalanceService,
    settings_service: SettingsService,
    quota_service: QuotaService,
):
    user_id = message.from_user.id
    state = _yt_state.get(user_id)
    if not state or not state.get("transcript_text"):
        state["ask_mode"] = False
        await message.answer("Контекст видео потерян. Отправьте ссылку заново.")
        return

    # Check if this is a new YouTube URL — let it fall through
    if YouTubeService.extract_video_id(message.text):
        state["ask_mode"] = False
        return  # Will be caught by handle_youtube_url below

    # Check token quota
    allowed, error_msg = await quota_service.check_tokens(user_id)
    if not allowed:
        await message.answer(error_msg, parse_mode="HTML")
        return

    question = message.text.strip()
    transcript = state["transcript_text"]
    title = state.get("title", "")

    # Truncate if needed
    if len(transcript) > MAX_TRANSCRIPT_CHARS:
        transcript = transcript[:MAX_TRANSCRIPT_CHARS] + "\n[...обрезано]"

    user_settings = await settings_service.get(user_id)
    provider = await ai_router.load_user_provider(user_id)
    service = ai_router.get_service(provider)

    context_msg = (
        f"Субтитры видео \"{title}\":\n\n{transcript}\n\n"
        f"Вопрос пользователя: {question}"
    )

    waiting = await message.answer("Отвечаю...")

    try:
        messages = [{"role": "user", "content": context_msg}]
        result = await service.generate(messages, system_prompt=SYSTEM_PROMPT)
        html = md_to_html(result)

        if len(html) <= 4000:
            await waiting.edit_text(html, parse_mode="HTML")
        else:
            await waiting.edit_text(html[:4000] + "...", parse_mode="HTML")

        if balance_service and service.last_usage:
            await balance_service.track_ai_usage(
                provider,
                service.last_usage["input_tokens"],
                service.last_usage["output_tokens"],
            )
        if quota_service and service.last_usage:
            total = service.last_usage["input_tokens"] + service.last_usage["output_tokens"]
            await quota_service.track_token_usage(user_id, total)
    except Exception as e:
        logger.exception("YouTube ask failed")
        await waiting.edit_text(f"Ошибка: {str(e)[:300]}")


# ═══════════════════════════════════════════════════════
#  URL DETECTION
# ═══════════════════════════════════════════════════════

@router.message(YouTubeURL(), F.text)
async def handle_youtube_url(message: Message, youtube_service: YouTubeService):
    video_id = YouTubeService.extract_video_id(message.text)
    if not video_id:
        return

    user_id = message.from_user.id
    # Reset ask mode
    if user_id in _yt_state:
        _yt_state[user_id]["ask_mode"] = False

    waiting = await message.answer("Загружаю информацию о видео...")

    try:
        info = await youtube_service.get_video_info(video_id)
    except Exception as e:
        logger.exception("Failed to get video info for %s", video_id)
        await waiting.edit_text(f"Не удалось получить информацию о видео: {str(e)[:200]}")
        return

    # Save state
    _yt_state[user_id] = {
        "video_id": video_id,
        "title": info.title,
        "channel": info.channel,
        "duration": info.duration,
        "transcript_text": None,
        "ask_mode": False,
    }

    dur = format_duration(info.duration)
    text = (
        f"<b>{info.title}</b>\n"
        f"{info.channel} | {dur}"
    )

    kb = get_youtube_menu(video_id)
    await waiting.edit_text(text, parse_mode="HTML", reply_markup=kb)


# ═══════════════════════════════════════════════════════
#  SUMMARIZE
# ═══════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("yt:sum:"))
async def on_summarize(
    callback: CallbackQuery,
    youtube_service: YouTubeService,
    ai_router: AIRouter,
    balance_service: BalanceService,
    settings_service: SettingsService,
    quota_service: QuotaService,
):
    video_id = callback.data.split(":")[2]
    user_id = callback.from_user.id
    state = _yt_state.get(user_id, {})

    # Check token quota
    allowed, error_msg = await quota_service.check_tokens(user_id)
    if not allowed:
        await callback.answer("Лимит токенов исчерпан", show_alert=True)
        return

    await callback.answer("Загружаю субтитры...")

    # Get transcript
    waiting = await callback.message.answer("Загружаю субтитры...")

    transcript = await youtube_service.get_transcript(video_id)
    if not transcript:
        await waiting.edit_text(
            "Субтитры недоступны для этого видео.\n"
            "Попробуйте видео с включёнными субтитрами."
        )
        return

    # Save transcript for ask mode
    state["transcript_text"] = transcript.text
    _yt_state[user_id] = state

    title = state.get("title", "")
    duration = state.get("duration", 0)

    await waiting.edit_text(
        f"Субтитры загружены ({transcript.language}, {len(transcript.text)} символов).\n"
        "Генерирую выжимку..."
    )

    user_settings = await settings_service.get(user_id)
    provider = await ai_router.load_user_provider(user_id)
    service = ai_router.get_service(provider)

    try:
        if duration > 7200:  # >2 hours — chunked summarization
            summary = await _summarize_long(
                transcript, title, service, provider, balance_service, quota_service, user_id
            )
        else:
            summary = await _summarize_short(
                transcript, title, service, provider, balance_service, quota_service, user_id
            )

        html = md_to_html(summary)

        if len(html) <= 4000:
            await waiting.edit_text(html, parse_mode="HTML", reply_markup=get_summary_keyboard(video_id))
        else:
            # Send as separate message, delete waiting
            await waiting.delete()
            # Split if needed
            for i in range(0, len(html), 4000):
                chunk = html[i:i + 4000]
                is_last = i + 4000 >= len(html)
                kb = get_summary_keyboard(video_id) if is_last else None
                await callback.message.answer(chunk, parse_mode="HTML", reply_markup=kb)

    except Exception as e:
        logger.exception("Summarization failed for %s", video_id)
        await waiting.edit_text(f"Ошибка суммаризации: {str(e)[:300]}")


async def _summarize_short(transcript, title, service, provider, balance_service, quota_service=None, user_id=None):
    """Summarize video ≤2h in one pass."""
    text = transcript.text
    if len(text) > MAX_TRANSCRIPT_CHARS:
        text = text[:MAX_TRANSCRIPT_CHARS] + "\n[...обрезано]"

    prompt = f"Видео: \"{title}\"\n\nСубтитры:\n{text}\n\n{SUMMARY_PROMPT}"
    messages = [{"role": "user", "content": prompt}]
    result = await service.generate(messages, system_prompt=SYSTEM_PROMPT)

    if balance_service and service.last_usage:
        await balance_service.track_ai_usage(
            provider, service.last_usage["input_tokens"], service.last_usage["output_tokens"]
        )
    if quota_service and user_id and service.last_usage:
        total = service.last_usage["input_tokens"] + service.last_usage["output_tokens"]
        await quota_service.track_token_usage(user_id, total)
    return result


async def _summarize_long(transcript, title, service, provider, balance_service, quota_service=None, user_id=None):
    """Summarize video >2h by chunking."""
    segments = transcript.segments
    chunks = []
    current_chunk = []
    chunk_start = 0

    for seg in segments:
        current_chunk.append(seg)
        elapsed = seg["start"] - chunk_start
        if elapsed >= CHUNK_DURATION and current_chunk:
            chunk_text = "\n".join(f"[{_ts(s['start'])}] {s['text']}" for s in current_chunk)
            chunks.append(chunk_text)
            current_chunk = []
            chunk_start = seg["start"]

    if current_chunk:
        chunk_text = "\n".join(f"[{_ts(s['start'])}] {s['text']}" for s in current_chunk)
        chunks.append(chunk_text)

    # Summarize each chunk
    partial_summaries = []
    for i, chunk in enumerate(chunks):
        if len(chunk) > MAX_TRANSCRIPT_CHARS:
            chunk = chunk[:MAX_TRANSCRIPT_CHARS]
        prompt = f"Видео: \"{title}\" (часть {i + 1}/{len(chunks)})\n\nСубтитры:\n{chunk}\n\n{CHUNK_SUMMARY_PROMPT}"
        messages = [{"role": "user", "content": prompt}]
        result = await service.generate(messages, system_prompt=SYSTEM_PROMPT)
        partial_summaries.append(result)

        if balance_service and service.last_usage:
            await balance_service.track_ai_usage(
                provider, service.last_usage["input_tokens"], service.last_usage["output_tokens"]
            )
        if quota_service and user_id and service.last_usage:
            total = service.last_usage["input_tokens"] + service.last_usage["output_tokens"]
            await quota_service.track_token_usage(user_id, total)

    # Merge summaries
    merged_input = "\n\n---\n\n".join(
        f"Часть {i + 1}:\n{s}" for i, s in enumerate(partial_summaries)
    )
    merge_prompt = f"Видео: \"{title}\"\n\n{merged_input}\n\n{MERGE_SUMMARY_PROMPT}"
    messages = [{"role": "user", "content": merge_prompt}]
    result = await service.generate(messages, system_prompt=SYSTEM_PROMPT)

    if balance_service and service.last_usage:
        await balance_service.track_ai_usage(
            provider, service.last_usage["input_tokens"], service.last_usage["output_tokens"]
        )
    if quota_service and user_id and service.last_usage:
        total = service.last_usage["input_tokens"] + service.last_usage["output_tokens"]
        await quota_service.track_token_usage(user_id, total)
    return result


def _ts(seconds: float) -> str:
    from bot.services.youtube_service import format_timestamp
    return format_timestamp(seconds)


# ═══════════════════════════════════════════════════════
#  BACK BUTTON
# ═══════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("yt:back:"))
async def on_back(callback: CallbackQuery):
    video_id = callback.data.split(":")[2]
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=get_youtube_menu(video_id))


# ═══════════════════════════════════════════════════════
#  ASK MODE ACTIVATION
# ═══════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("yt:ask:"))
async def on_ask_mode(callback: CallbackQuery):
    user_id = callback.from_user.id
    state = _yt_state.get(user_id)

    if not state or not state.get("transcript_text"):
        await callback.answer("Субтитры не загружены. Сначала нажмите Выжимка.", show_alert=True)
        return

    state["ask_mode"] = True
    await callback.answer("Режим вопросов активирован")
    await callback.message.answer(
        "Задайте вопрос по видео. Субтитры в контексте.\n"
        "Для выхода отправьте любую команду или новую ссылку."
    )


# ═══════════════════════════════════════════════════════
#  VIDEO DOWNLOAD
# ═══════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("yt:vid:"))
async def on_video_menu(callback: CallbackQuery):
    video_id = callback.data.split(":")[2]
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=get_video_quality_keyboard(video_id))


@router.callback_query(F.data.startswith("yt:vq:"))
async def on_download_video(
    callback: CallbackQuery,
    youtube_service: YouTubeService,
    quota_service: QuotaService,
):
    user_id = callback.from_user.id

    # Check YouTube download access
    allowed, error_msg = await quota_service.check_youtube(user_id)
    if not allowed:
        await callback.answer("Скачивание YouTube недоступно в вашем плане", show_alert=True)
        return

    parts = callback.data.split(":")
    video_id = parts[2]
    quality = parts[3]
    state = _yt_state.get(user_id, {})
    title = state.get("title", "video")

    await callback.answer("Скачиваю...")
    label = f"Скачиваю видео ({quality})..."
    waiting = await callback.message.answer(label)

    filepath = None
    try:
        progress = _make_progress_callback(waiting, label)
        filepath, filesize = await youtube_service.download_video(
            video_id, quality, progress_callback=progress,
        )

        if filesize > youtube_service.max_file_size:
            size_mb = filesize / (1024 * 1024)
            limit_mb = youtube_service.max_file_size / (1024 * 1024)
            await waiting.edit_text(
                f"Файл слишком большой: {size_mb:.0f}MB (лимит {limit_mb:.0f}MB).\n"
                "Попробуйте ниже качество.",
                reply_markup=get_video_quality_keyboard(video_id),
            )
            return

        size_mb = filesize / (1024 * 1024)

        if filesize > LARGE_FILE_WARNING:
            await waiting.edit_text(f"Отправляю большой файл ({size_mb:.0f}MB), подождите...")
        else:
            await waiting.edit_text("Отправляю...")

        safe_title = "".join(c for c in title if c.isalnum() or c in " -_")[:50]

        if filesize > MAX_FILE_SIZE_CLOUD and youtube_service.use_local_api:
            # Large file with Local API — use FSInputFile (no RAM overhead)
            video_file = FSInputFile(filepath, filename=f"{safe_title}.mp4")
        else:
            with open(filepath, "rb") as f:
                video_data = f.read()
            video_file = BufferedInputFile(video_data, filename=f"{safe_title}.mp4")

        await callback.message.answer_video(
            video=video_file,
            caption=f"{title} | {quality} | {size_mb:.1f}MB",
        )
        await waiting.delete()

    except Exception as e:
        logger.exception("Video download failed for %s", video_id)
        await waiting.edit_text(f"Ошибка скачивания: {str(e)[:300]}")
    finally:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)


# ═══════════════════════════════════════════════════════
#  AUDIO DOWNLOAD
# ═══════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("yt:aud:"))
async def on_audio_menu(callback: CallbackQuery):
    video_id = callback.data.split(":")[2]
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=get_audio_format_keyboard(video_id))


@router.callback_query(F.data.startswith("yt:af:"))
async def on_download_audio(
    callback: CallbackQuery,
    youtube_service: YouTubeService,
    quota_service: QuotaService,
):
    user_id = callback.from_user.id

    # Check YouTube download access
    allowed, error_msg = await quota_service.check_youtube(user_id)
    if not allowed:
        await callback.answer("Скачивание YouTube недоступно в вашем плане", show_alert=True)
        return

    parts = callback.data.split(":")
    video_id = parts[2]
    fmt = parts[3]
    state = _yt_state.get(user_id, {})
    title = state.get("title", "audio")
    channel = state.get("channel", "")

    fmt_labels = {"mp3_128": "MP3 128kbps", "mp3_320": "MP3 320kbps", "wav": "WAV"}
    fmt_label = fmt_labels.get(fmt, fmt)

    await callback.answer("Скачиваю...")
    label = f"Скачиваю аудио ({fmt_label})..."
    waiting = await callback.message.answer(label)

    filepath = None
    try:
        progress = _make_progress_callback(waiting, label)
        filepath, filesize = await youtube_service.download_audio(
            video_id, fmt, progress_callback=progress,
        )

        if filesize > youtube_service.max_file_size:
            size_mb = filesize / (1024 * 1024)
            limit_mb = youtube_service.max_file_size / (1024 * 1024)
            await waiting.edit_text(
                f"Файл слишком большой: {size_mb:.0f}MB (лимит {limit_mb:.0f}MB).\n"
                "Попробуйте формат с меньшим битрейтом.",
                reply_markup=get_audio_format_keyboard(video_id),
            )
            return

        size_mb = filesize / (1024 * 1024)

        if filesize > LARGE_FILE_WARNING:
            await waiting.edit_text(f"Отправляю большой файл ({size_mb:.0f}MB), подождите...")
        else:
            await waiting.edit_text("Отправляю...")

        ext = "mp3" if fmt.startswith("mp3") else "wav"
        safe_title = "".join(c for c in title if c.isalnum() or c in " -_")[:50]

        if filesize > MAX_FILE_SIZE_CLOUD and youtube_service.use_local_api:
            audio_file = FSInputFile(filepath, filename=f"{safe_title}.{ext}")
        else:
            with open(filepath, "rb") as f:
                audio_data = f.read()
            audio_file = BufferedInputFile(audio_data, filename=f"{safe_title}.{ext}")

        await callback.message.answer_audio(
            audio=audio_file,
            title=title,
            performer=channel,
            caption=f"{fmt_label} | {size_mb:.1f}MB",
        )
        await waiting.delete()

    except Exception as e:
        logger.exception("Audio download failed for %s", video_id)
        await waiting.edit_text(f"Ошибка скачивания: {str(e)[:300]}")
    finally:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
