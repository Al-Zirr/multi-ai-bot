"""Image generation service: DALL-E 3 + Gemini Imagen 3 + BFL Flux 2 Pro."""

import asyncio
import logging
from dataclasses import dataclass

import aiohttp
from openai import AsyncOpenAI
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

DALLE_PRICING = {
    ("standard", "1024x1024"): 0.040,
    ("standard", "1792x1024"): 0.080,
    ("standard", "1024x1792"): 0.080,
    ("hd", "1024x1024"): 0.080,
    ("hd", "1792x1024"): 0.120,
    ("hd", "1024x1792"): 0.120,
}

IMAGEN_PRICE_PER_IMAGE = 0.04

# BFL Flux 2 Pro: ~$0.05 per image
FLUX_PRICE_PER_IMAGE = 0.05

BFL_API_URL = "https://api.bfl.ai/v1/flux-2-pro"


@dataclass
class ImageGenParams:
    prompt: str
    provider: str = "dalle"
    size: str = "1024x1024"
    style: str = "vivid"
    quality: str = "standard"


@dataclass
class ImageResult:
    image_data: bytes
    provider: str
    revised_prompt: str | None
    size: str
    cost: float


class ImageService:
    def __init__(
        self,
        openai_api_key: str = "",
        google_api_key: str = "",
        bfl_api_key: str = "",
    ):
        self._providers: list[str] = []

        if openai_api_key:
            self._openai = AsyncOpenAI(api_key=openai_api_key)
            self._providers.append("dalle")
            logger.info("ImageService: DALL-E enabled")
        else:
            self._openai = None

        if google_api_key:
            self._google = genai.Client(api_key=google_api_key)
            self._providers.append("imagen")
            logger.info("ImageService: Imagen enabled")
        else:
            self._google = None

        self._bfl_api_key = bfl_api_key
        if bfl_api_key:
            self._providers.append("flux")
            logger.info("ImageService: Flux 2 Pro enabled")

    def available_providers(self) -> list[str]:
        return list(self._providers)

    async def generate(self, params: ImageGenParams) -> ImageResult:
        if params.provider == "dalle":
            if not self._openai:
                raise RuntimeError("DALL-E not configured")
            return await self._generate_dalle(params)
        elif params.provider == "imagen":
            if not self._google:
                raise RuntimeError("Imagen not configured")
            return await self._generate_imagen(params)
        elif params.provider == "flux":
            if not self._bfl_api_key:
                raise RuntimeError("Flux not configured")
            return await self._generate_flux(params)
        else:
            raise ValueError(f"Unknown provider: {params.provider}")

    async def _generate_dalle(self, params: ImageGenParams) -> ImageResult:
        response = await self._openai.images.generate(
            model="dall-e-3",
            prompt=params.prompt,
            size=params.size,
            style=params.style,
            quality=params.quality,
            n=1,
            response_format="url",
        )

        image_url = response.data[0].url
        revised_prompt = response.data[0].revised_prompt

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                image_data = await resp.read()

        cost = DALLE_PRICING.get((params.quality, params.size), 0.040)

        logger.info(
            "DALL-E generated: size=%s quality=%s style=%s cost=$%.3f",
            params.size, params.quality, params.style, cost,
        )

        return ImageResult(
            image_data=image_data,
            provider="dalle",
            revised_prompt=revised_prompt,
            size=params.size,
            cost=cost,
        )

    async def _generate_imagen(self, params: ImageGenParams) -> ImageResult:
        response = await self._google.aio.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=params.prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
            ),
        )

        if not response.generated_images:
            raise RuntimeError("Imagen returned no images")

        image_data = response.generated_images[0].image.image_bytes

        logger.info("Imagen generated: cost=$%.3f", IMAGEN_PRICE_PER_IMAGE)

        return ImageResult(
            image_data=image_data,
            provider="imagen",
            revised_prompt=None,
            size="1024x1024",
            cost=IMAGEN_PRICE_PER_IMAGE,
        )

    async def _generate_flux(self, params: ImageGenParams) -> ImageResult:
        """Generate image via BFL Flux 2 Pro (async polling)."""
        # Parse size
        parts = params.size.split("x")
        width = int(parts[0])
        height = int(parts[1])

        headers = {
            "accept": "application/json",
            "x-key": self._bfl_api_key,
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            # Submit generation request
            async with session.post(
                BFL_API_URL,
                headers=headers,
                json={
                    "prompt": params.prompt,
                    "width": width,
                    "height": height,
                },
            ) as resp:
                if resp.status == 402:
                    raise RuntimeError("BFL: insufficient credits")
                if resp.status == 429:
                    raise RuntimeError("BFL: rate limit exceeded")
                resp.raise_for_status()
                submit_data = await resp.json()

            polling_url = submit_data.get("polling_url")
            if not polling_url:
                raise RuntimeError(f"BFL: no polling_url in response: {submit_data}")

            # Poll for result (max 120 seconds)
            poll_headers = {
                "accept": "application/json",
                "x-key": self._bfl_api_key,
            }
            for _ in range(240):
                await asyncio.sleep(0.5)
                async with session.get(polling_url, headers=poll_headers) as poll_resp:
                    poll_data = await poll_resp.json()

                status = poll_data.get("status")
                if status == "Ready":
                    image_url = poll_data["result"]["sample"]
                    break
                elif status in ("Error", "Failed"):
                    raise RuntimeError(f"BFL generation failed: {poll_data}")
            else:
                raise RuntimeError("BFL: generation timed out (120s)")

            # Download image
            async with session.get(image_url) as img_resp:
                image_data = await img_resp.read()

        logger.info(
            "Flux 2 Pro generated: %dx%d cost=$%.3f",
            width, height, FLUX_PRICE_PER_IMAGE,
        )

        return ImageResult(
            image_data=image_data,
            provider="flux",
            revised_prompt=None,
            size=params.size,
            cost=FLUX_PRICE_PER_IMAGE,
        )
