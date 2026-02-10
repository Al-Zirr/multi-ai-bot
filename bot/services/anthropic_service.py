import base64
import logging
from collections.abc import AsyncGenerator

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


class AnthropicService:
    PROVIDER = "claude"
    DISPLAY_NAME = "Claude"

    def __init__(self, api_key: str, model: str):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.last_usage: dict | None = None

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
    ) -> AsyncGenerator[str, None]:
        self.last_usage = None
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        async with self.client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

            msg = await stream.get_final_message()
            if msg and msg.usage:
                self.last_usage = {
                    "input_tokens": msg.usage.input_tokens or 0,
                    "output_tokens": msg.usage.output_tokens or 0,
                }

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
        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": mime_type, "data": b64},
                },
                {"type": "text", "text": prompt},
            ],
        }]
        kwargs = {"model": self.model, "messages": messages, "max_tokens": 4096}
        if system_prompt:
            kwargs["system"] = system_prompt
        response = await self.client.messages.create(**kwargs)
        if response.usage:
            self.last_usage = {
                "input_tokens": response.usage.input_tokens or 0,
                "output_tokens": response.usage.output_tokens or 0,
            }
        return response.content[0].text if response.content else ""
