import logging
from collections.abc import AsyncGenerator

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Fallback chain for 429 rate limit errors
GEMINI_FALLBACK_CHAIN = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]


class GeminiService:
    PROVIDER = "gemini"
    DISPLAY_NAME = "Gemini"

    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model
        self.last_usage: dict | None = None
        self._build_fallback_chain()

    def _build_fallback_chain(self):
        """Build fallback list: current model first, then remaining from chain."""
        self._fallback_models = [self.model_name]
        for m in GEMINI_FALLBACK_CHAIN:
            if m != self.model_name:
                self._fallback_models.append(m)

    def _is_rate_limit(self, err: Exception) -> bool:
        """Check if error is a 429 rate limit."""
        err_str = str(err)
        return "429" in err_str or "RESOURCE_EXHAUSTED" in err_str

    def _build_contents(
        self, messages: list[dict[str, str]]
    ) -> list[types.Content]:
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=msg["content"])],
                )
            )
        return contents

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
    ) -> AsyncGenerator[str, None]:
        self.last_usage = None
        contents = self._build_contents(messages)

        config = types.GenerateContentConfig()
        if system_prompt:
            config.system_instruction = system_prompt

        last_err = None
        for model in self._fallback_models:
            try:
                stream = await self.client.aio.models.generate_content_stream(
                    model=model,
                    contents=contents,
                    config=config,
                )
                got_tokens = False
                async for chunk in stream:
                    if chunk.text:
                        got_tokens = True
                        yield chunk.text
                    if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                        um = chunk.usage_metadata
                        self.last_usage = {
                            "input_tokens": getattr(um, "prompt_token_count", 0) or 0,
                            "output_tokens": getattr(um, "candidates_token_count", 0) or 0,
                        }
                if got_tokens:
                    if model != self.model_name:
                        logger.info("Gemini fallback to %s succeeded (stream)", model)
                    return
            except Exception as err:
                last_err = err
                if self._is_rate_limit(err):
                    logger.warning("Gemini 429 on %s, trying next fallback", model)
                    continue
                # Non-429 error on primary model — try non-streaming
                logger.warning("Gemini streaming failed on %s: %s", model, err)
                try:
                    response = await self.client.aio.models.generate_content(
                        model=model,
                        contents=contents,
                        config=config,
                    )
                    if response.text:
                        if hasattr(response, "usage_metadata") and response.usage_metadata:
                            um = response.usage_metadata
                            self.last_usage = {
                                "input_tokens": getattr(um, "prompt_token_count", 0) or 0,
                                "output_tokens": getattr(um, "candidates_token_count", 0) or 0,
                            }
                        yield response.text
                        return
                except Exception as sync_err:
                    last_err = sync_err
                    if self._is_rate_limit(sync_err):
                        logger.warning("Gemini 429 on %s (non-stream), trying next", model)
                        continue
                    raise

        # All fallbacks exhausted
        if last_err:
            raise last_err

    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
    ) -> str:
        result = []
        async for token in self.generate_stream(messages, system_prompt):
            result.append(token)
        return "".join(result)

    async def generate_with_image(
        self, image_data: bytes, mime_type: str, prompt: str, system_prompt: str = ""
    ) -> str:
        """Analyze image using Vision API."""
        self.last_usage = None
        config = types.GenerateContentConfig()
        if system_prompt:
            config.system_instruction = system_prompt

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=image_data, mime_type=mime_type),
                    types.Part(text=prompt),
                ],
            )
        ]

        last_err = None
        for model in self._fallback_models:
            try:
                response = await self.client.aio.models.generate_content(
                    model=model, contents=contents, config=config
                )
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    um = response.usage_metadata
                    self.last_usage = {
                        "input_tokens": getattr(um, "prompt_token_count", 0) or 0,
                        "output_tokens": getattr(um, "candidates_token_count", 0) or 0,
                    }
                if model != self.model_name:
                    logger.info("Gemini fallback to %s succeeded (vision)", model)
                return response.text or ""
            except Exception as err:
                last_err = err
                if self._is_rate_limit(err):
                    logger.warning("Gemini 429 on %s (vision), trying next", model)
                    continue
                raise

        if last_err:
            raise last_err
        return ""
