"""Background worker that checks for new OLX items and notifies users.

Single Responsibility: orchestrates *sending* notifications – it does not know
anything about Telegram handlers or database internals.  It depends only on
(1) an aiogram ``Bot`` instance for I/O and (2) the high-level
``MonitoringService`` abstraction for business queries.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING, Final

import aiohttp
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile
from PIL import Image

from bot.responses import ITEMS_FOUND_CAPTION
from core.config import settings
from services.monitoring import MonitoringService

if TYPE_CHECKING:
    import redis.asyncio as redis

logger: Final = logging.getLogger(__name__)


class Notifier:  # noqa: D101 – simple name
    def __init__(self, bot: Bot, service: MonitoringService, redis_client: redis.Redis):
        self._bot = bot
        self._svc = service
        self._redis = redis_client
        # Image cache TTL in seconds (converted from days)
        self._image_cache_ttl = settings.IMAGE_CACHE_TTL_DAYS * 86400

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    async def run_periodically(
        self, interval_s: int
    ) -> None:  # noqa: D401 – simple name
        """Run background check forever sleeping *interval_s* between cycles."""
        while True:
            try:
                await self._check_and_send_items()
            except Exception:  # pragma: no cover – log unexpected
                logger.exception("Unexpected error during periodic check")
            logger.info("Sleeping for %s seconds", interval_s)
            await asyncio.sleep(interval_s)

    # ------------------------------------------------------------------
    # Internal helpers (should be small & testable)
    # ------------------------------------------------------------------
    async def _check_and_send_items(self) -> None:  # noqa: D401 – simple name
        """Check for new items and notify users."""
        pending_tasks = await self._svc.pending_tasks()

        for task in pending_tasks:
            items_to_send = await self._svc.items_to_send(task)
            logger.info(
                "Found %d items to send for chat_id %s",
                len(items_to_send),
                task.chat_id,
            )

            if not items_to_send:
                # Mark that we *did* check – useful for monitoring dashboards
                await self._svc.update_last_updated(task)
                continue

            # Notify user that N items were found
            await self._bot.send_photo(
                chat_id=task.chat_id,
                photo="https://tse4.mm.bing.net/th?id=OIG2.fso8nlFWoq9hafRkva2e&pid=ImgGn",
                caption=ITEMS_FOUND_CAPTION.format(
                    count=len(items_to_send), monitoring=task.name
                ),
            )

            for item in reversed(items_to_send):
                text = _format_item_text(item)
                # Handle both dict and object access patterns for image_url
                image_url = (
                    item.get("image_url")
                    if isinstance(item, dict)
                    else getattr(item, "image_url", None)
                )

                if image_url:
                    await self._send_item_with_image(task.chat_id, image_url, text)
                else:
                    await self._bot.send_message(
                        chat_id=task.chat_id, text=text, parse_mode="MarkdownV2"
                    )
                await asyncio.sleep(0.5)  # prevent Telegram Flood-wait

            # Persist bookkeeping timestamps
            await self._svc.update_last_got_item(task.chat_id)
            await self._svc.update_last_updated(task)

    async def _send_item_with_image(
        self, chat_id: int, image_url: str, text: str
    ) -> None:
        """Send item with intelligent image handling and fallbacks.

        Uses a multi-layer fallback strategy:
        1. Try cached file_id (instant, no network)
        2. Try direct URL (works for most CDNs)
        3. Try fetching with browser headers (for restrictive CDNs)
        4. Fall back to text message (always works)
        """
        # Layer 1: Try cached file_id
        cached_file_id = await self._redis.get(f"photo:{image_url}")
        if cached_file_id:
            try:
                await self._bot.send_photo(
                    chat_id=chat_id,
                    photo=cached_file_id,
                    caption=text,
                    parse_mode="MarkdownV2",
                )
                return  # Success!
            except Exception:
                # File_id expired or invalid, remove from cache
                await self._redis.delete(f"photo:{image_url}")
                logger.debug("Cached file_id expired, trying other methods")

        # Layer 2: Try direct URL
        try:
            message = await self._bot.send_photo(
                chat_id=chat_id,
                photo=image_url,
                caption=text,
                parse_mode="MarkdownV2",
            )
            # Cache the file_id for future use
            file_id = message.photo[-1].file_id
            await self._redis.set(
                f"photo:{image_url}", file_id, ex=self._image_cache_ttl
            )
            return  # Success!
        except TelegramBadRequest as e:
            logger.info("Direct URL failed: %s. Trying with custom headers...", e)

        # Layer 3: Try fetching with browser-like headers
        image_file = await self._fetch_image_with_headers(image_url)
        if image_file:
            try:
                message = await self._bot.send_photo(
                    chat_id=chat_id,
                    photo=image_file,
                    caption=text,
                    parse_mode="MarkdownV2",
                )
                # Cache the file_id we just got
                file_id = message.photo[-1].file_id
                await self._redis.set(
                    f"photo:{image_url}", file_id, ex=self._image_cache_ttl
                )
                return  # Success!
            except Exception as e:
                logger.warning("Failed to send fetched image: %s", e)

        # Layer 4: Give up on image, send as text
        logger.warning("All image methods failed for %s. Sending as text.", image_url)
        await self._bot.send_message(
            chat_id=chat_id, text=text, parse_mode="MarkdownV2"
        )

    async def _fetch_image_with_headers(self, url: str) -> BufferedInputFile | None:
        """Fetch image with browser headers for CDN compatibility.

        Automatically resizes images that exceed Telegram's dimension limits.
        Returns BufferedInputFile if successful, None if failed.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get("Content-Type", "")
                        if "image" in content_type:
                            image_data = await resp.read()

                            # Resize if needed to meet Telegram's requirements
                            resized_data = self._resize_image_if_needed(image_data)
                            if resized_data:
                                return BufferedInputFile(
                                    resized_data, filename="image.jpg"
                                )
        except Exception as e:
            logger.debug("Failed to fetch image with headers: %s", e)
        return None

    def _resize_image_if_needed(self, image_data: bytes) -> bytes | None:
        """Resize image if it exceeds Telegram's dimension limits.

        Telegram requirements:
        - Width + Height <= 10,000 pixels
        - Max dimension <= 10,000 pixels
        - File size <= 10 MB

        Returns resized image as JPEG bytes, or None if processing fails.
        """
        try:
            img = Image.open(BytesIO(image_data))
            width, height = img.size

            # Check if resizing is needed
            max_dimension = 10000
            max_sum = 10000

            if (
                width + height <= max_sum
                and width <= max_dimension
                and height <= max_dimension
            ):
                # Image is fine, return original
                return image_data

            # Calculate new dimensions while preserving aspect ratio
            # Target: width + height = 9500 (leaving some margin)
            target_sum = 9500
            ratio = width / height

            # Solve: new_width + new_height = target_sum
            # where new_width / new_height = ratio
            new_height = int(target_sum / (ratio + 1))
            new_width = int(new_height * ratio)

            logger.info(
                "Resizing image from %dx%d to %dx%d to meet Telegram limits",
                width,
                height,
                new_width,
                new_height,
            )

            # Resize with high-quality settings
            img = img.convert("RGB")  # Ensure RGB mode for JPEG
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Save to bytes
            output = BytesIO()
            img.save(output, format="JPEG", quality=85, optimize=True)
            return output.getvalue()

        except Exception as e:
            logger.warning("Failed to resize image: %s", e)
            return None


# ---------------------------- Formatting helpers -----------------------------


def _escape_markdown_v2(text: str) -> str:
    """
    Escape all special characters for Telegram MarkdownV2.
    """
    if not text:
        return text
    # All special characters that need escaping in MarkdownV2
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    for char in escape_chars:
        text = text.replace(char, rf"\{char}")
    return text


def bold_telegram_md(text: str) -> str:
    """
    Safely wrap user content in *...* for Telegram MarkdownV2.
    Escapes all special characters before wrapping.
    """
    if not text:
        return ""
    text = _escape_markdown_v2(text)
    return f"*{text}*"


def _format_item_text(item) -> str:  # type: ignore[annotation-unreachable]
    """Return Markdown-formatted text for *item* compatible with Telegram."""
    # Handle both dict and object access patterns
    description = (
        item.get("description", "")
        if isinstance(item, dict)
        else getattr(item, "description", "")
    )
    desc_lines = description.strip().split("\n")
    extra = {}
    for line in desc_lines:
        if line.startswith("price:"):
            extra["price_info"] = line.replace("price:", "Price:").strip()
        elif line.startswith("deposit:"):
            extra["deposit_info"] = line.replace("deposit:", "Deposit:").strip()
        elif line.startswith("animals_allowed:"):
            animals_allowed = line.replace("animals_allowed:", "").strip()
            if animals_allowed == "true":
                extra["animals_info"] = "Pets: Allowed"
            elif animals_allowed == "false":
                extra["animals_info"] = "Pets: Not allowed"
        elif line.startswith("rent:"):
            extra["rent_info"] = line.replace("rent:", "Additional rent:").strip()

    # Extract item fields with dict/object compatibility
    title = (
        item.get("title", "No title")
        if isinstance(item, dict)
        else getattr(item, "title", "No title")
    )
    price = (
        item.get("price", "N/A")
        if isinstance(item, dict)
        else getattr(item, "price", "N/A")
    )
    location = (
        item.get("location", "N/A")
        if isinstance(item, dict)
        else getattr(item, "location", "N/A")
    )
    created_at = (
        item.get("created_at", "N/A")
        if isinstance(item, dict)
        else getattr(item, "created_at", "N/A")
    )
    item_url = (
        item.get("item_url", "#")
        if isinstance(item, dict)
        else getattr(item, "item_url", "#")
    )
    source = (
        item.get("source") if isinstance(item, dict) else getattr(item, "source", None)
    )

    # Format and escape all user-provided content for MarkdownV2
    title_bold = bold_telegram_md(title)
    price_escaped = _escape_markdown_v2(str(price))
    location_escaped = _escape_markdown_v2(str(location))

    # Format created_at from ISO format to readable format with bold time
    if created_at and created_at != "N/A":
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            date_part = dt.strftime("%d.%m.%Y")
            time_part = dt.strftime("%H:%M")
            # Build the full date string, then escape and bold appropriately
            date_formatted = f"{_escape_markdown_v2(date_part)} {_escape_markdown_v2('-')} {bold_telegram_md(time_part)}"
        except (ValueError, AttributeError):
            date_formatted = _escape_markdown_v2(str(created_at))
    else:
        date_formatted = "N/A"

    text = (
        f"📦 {title_bold}\n\n"
        f"💰 {bold_telegram_md('Price')}: {price_escaped}\n"
        f"📍 {bold_telegram_md('Location')}: {location_escaped}\n"
        f"🕒 {bold_telegram_md('Posted')}: {date_formatted}\n"
    )
    # Optional extras
    if price_info := extra.get("price_info"):
        text += f"💵 {bold_telegram_md('Price')}: {price_info}\n"
    if (deposit := extra.get("deposit_info")) and deposit != "Deposit: 0":
        text += f"🔐 {bold_telegram_md('Deposit')}: {deposit}\n"
    if animals := extra.get("animals_info"):
        text += f"🐾 {bold_telegram_md('Animals')}: {animals}\n"
    if rent := extra.get("rent_info"):
        text += f"💳 {bold_telegram_md('Rent')}: {rent}\n"

    platform_name = _escape_markdown_v2(source if source else "Unknown source")
    item_url_escaped = _escape_markdown_v2(item_url)
    text += f"🔗 [View on {platform_name}]({item_url_escaped})"
    return text
