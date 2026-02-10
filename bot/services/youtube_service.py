"""YouTube service: video info, transcripts, downloads."""

import asyncio
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

YOUTUBE_RE = re.compile(
    r"(?:https?://)?(?:www\.|m\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)"
    r"([a-zA-Z0-9_-]{11})"
)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB Telegram limit

# Preferred subtitle languages in order
SUBTITLE_LANGS = ["ru", "ar", "en"]


@dataclass
class VideoInfo:
    video_id: str
    title: str
    channel: str
    duration: int  # seconds
    url: str


@dataclass
class TranscriptResult:
    text: str
    language: str
    segments: list[dict] = field(default_factory=list)


def format_duration(seconds: int) -> str:
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_timestamp(seconds: float) -> str:
    s = int(seconds)
    h, remainder = divmod(s, 3600)
    m, sec = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


COOKIES_PATH = "/app/files/youtube_cookies.txt"


class YouTubeService:
    def __init__(self, proxy: str | None = None, files_dir: str = "/app/files"):
        self.proxy = proxy
        self.files_dir = files_dir
        self._tmp_dir = os.path.join(files_dir, "yt_tmp")
        os.makedirs(self._tmp_dir, exist_ok=True)

    @staticmethod
    def extract_video_id(text: str) -> str | None:
        match = YOUTUBE_RE.search(text)
        return match.group(1) if match else None

    def _base_opts(self) -> dict:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "js_runtimes": {"node": {}},
        }
        if os.path.exists(COOKIES_PATH):
            opts["cookiefile"] = COOKIES_PATH
        if self.proxy:
            opts["proxy"] = self.proxy
        return opts

    async def get_video_info(self, video_id: str) -> VideoInfo:
        opts = self._base_opts()
        opts["skip_download"] = True

        def _extract():
            import yt_dlp
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                return VideoInfo(
                    video_id=video_id,
                    title=info.get("title", "Unknown"),
                    channel=info.get("channel", info.get("uploader", "Unknown")),
                    duration=int(info.get("duration", 0)),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                )

        return await asyncio.get_event_loop().run_in_executor(None, _extract)

    async def get_transcript(self, video_id: str) -> TranscriptResult | None:
        def _fetch():
            from youtube_transcript_api import YouTubeTranscriptApi
            from youtube_transcript_api._errors import (
                TranscriptsDisabled,
                NoTranscriptFound,
                VideoUnavailable,
            )

            api = YouTubeTranscriptApi()

            try:
                transcript_list = api.list(video_id)
            except (TranscriptsDisabled, VideoUnavailable):
                return None

            # Try preferred languages first (manual)
            for lang in SUBTITLE_LANGS:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    fetched = transcript.fetch()
                    segments = self._fetched_to_segments(fetched)
                    text = self._segments_to_text(segments)
                    return TranscriptResult(text=text, language=lang, segments=segments)
                except NoTranscriptFound:
                    continue

            # Try auto-generated
            for lang in SUBTITLE_LANGS:
                try:
                    transcript = transcript_list.find_generated_transcript([lang])
                    fetched = transcript.fetch()
                    segments = self._fetched_to_segments(fetched)
                    text = self._segments_to_text(segments)
                    return TranscriptResult(text=text, language=f"{lang}-auto", segments=segments)
                except NoTranscriptFound:
                    continue

            # Fallback: any available transcript
            try:
                for transcript in transcript_list:
                    fetched = transcript.fetch()
                    segments = self._fetched_to_segments(fetched)
                    text = self._segments_to_text(segments)
                    return TranscriptResult(
                        text=text,
                        language=transcript.language_code,
                        segments=segments,
                    )
            except Exception:
                pass

            return None

        try:
            return await asyncio.get_event_loop().run_in_executor(None, _fetch)
        except Exception:
            logger.exception("Failed to get transcript for %s", video_id)
            return None

    @staticmethod
    def _fetched_to_segments(fetched) -> list[dict]:
        """Convert FetchedTranscript snippets to list of dicts."""
        return [{"start": s.start, "text": s.text} for s in fetched]

    @staticmethod
    def _segments_to_text(segments: list[dict]) -> str:
        """Convert transcript segments to text with timestamps."""
        lines = []
        for seg in segments:
            ts = format_timestamp(seg["start"])
            text = seg["text"].strip()
            if text:
                lines.append(f"[{ts}] {text}")
        return "\n".join(lines)

    @staticmethod
    def segments_plain_text(segments: list[dict]) -> str:
        """Plain text without timestamps (for AI context)."""
        return " ".join(seg["text"].strip() for seg in segments if seg["text"].strip())

    def _progress_hook(self, progress_callback, loop):
        """Create a yt-dlp progress hook that bridges to asyncio."""
        last_update = [0.0]

        def hook(d):
            if d["status"] != "downloading" or not progress_callback:
                return
            now = time.time()
            if now - last_update[0] < 2:
                return
            last_update[0] = now
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                asyncio.run_coroutine_threadsafe(
                    progress_callback(downloaded, total), loop,
                )

        return hook

    def _postprocessor_hook(self, progress_callback, loop):
        """Create a yt-dlp postprocessor hook for FFmpeg phase."""

        def hook(d):
            if d["status"] == "started" and progress_callback:
                asyncio.run_coroutine_threadsafe(
                    progress_callback(0, 0), loop,
                )

        return hook

    async def download_video(
        self, video_id: str, quality: str = "best", progress_callback=None,
    ) -> tuple[str, int]:
        """Download video. Returns (filepath, filesize). Caller must delete file."""
        if quality == "best":
            fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        else:
            h = int(quality)
            fmt = (
                f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={h}]+bestaudio/"
                f"best[height<={h}]"
            )

        out_path = os.path.join(self._tmp_dir, f"{video_id}_v.%(ext)s")
        opts = self._base_opts()
        opts.update({
            "format": fmt,
            "outtmpl": out_path,
            "merge_output_format": "mp4",
        })

        loop = asyncio.get_event_loop()
        if progress_callback:
            opts["progress_hooks"] = [self._progress_hook(progress_callback, loop)]

        def _download():
            import yt_dlp
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
                filename = ydl.prepare_filename(info)
                # yt-dlp may change extension after merge
                if not os.path.exists(filename):
                    filename = filename.rsplit(".", 1)[0] + ".mp4"
                return filename

        filepath = await loop.run_in_executor(None, _download)
        filesize = os.path.getsize(filepath)
        return filepath, filesize

    async def download_audio(
        self, video_id: str, fmt: str = "mp3_128", progress_callback=None,
    ) -> tuple[str, int]:
        """Download audio. Returns (filepath, filesize). Caller must delete file."""
        out_path = os.path.join(self._tmp_dir, f"{video_id}_a.%(ext)s")
        opts = self._base_opts()
        opts.update({
            "format": "bestaudio/best",
            "outtmpl": out_path,
        })

        if fmt == "mp3_128":
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }]
        elif fmt == "mp3_320":
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }]
        elif fmt == "wav":
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }]

        loop = asyncio.get_event_loop()
        if progress_callback:
            opts["progress_hooks"] = [self._progress_hook(progress_callback, loop)]
            opts["postprocessor_hooks"] = [self._postprocessor_hook(progress_callback, loop)]

        def _download():
            import yt_dlp
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
                filename = ydl.prepare_filename(info)
                # Extension changes after postprocessing
                base = filename.rsplit(".", 1)[0]
                ext = "mp3" if fmt.startswith("mp3") else "wav"
                final = base + "." + ext
                if os.path.exists(final):
                    return final
                # Fallback: find any file matching pattern
                for f in os.listdir(self._tmp_dir):
                    if f.startswith(f"{video_id}_a."):
                        return os.path.join(self._tmp_dir, f)
                return filename

        filepath = await asyncio.get_event_loop().run_in_executor(None, _download)
        filesize = os.path.getsize(filepath)
        return filepath, filesize
