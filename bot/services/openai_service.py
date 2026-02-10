import base64
import logging
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class OpenAIService:
    PROVIDER = "gpt"
    DISPLAY_NAME = "GPT"

    def __init__(self, api_key: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.last_usage: dict | None = None

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
    ) -> AsyncGenerator[str, None]:
        self.last_usage = None
        api_messages: list[dict[str, str]] = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(messages)

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=api_messages,
            stream=True,
            stream_options={"include_usage": True},
            max_completion_tokens=4096,
        )

        async for chunk in stream:
            if chunk.usage:
                self.last_usage = {
                    "input_tokens": chunk.usage.prompt_tokens or 0,
                    "output_tokens": chunk.usage.completion_tokens or 0,
                }
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

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
        b64 = base64.b64encode(image_data).decode()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        })
        response = await self.client.chat.completions.create(
            model=self.model, messages=messages, max_completion_tokens=4096
        )
        if response.usage:
            self.last_usage = {
                "input_tokens": response.usage.prompt_tokens or 0,
                "output_tokens": response.usage.completion_tokens or 0,
            }
        return response.choices[0].message.content or ""
