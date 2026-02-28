import asyncio
import unittest
from io import BytesIO
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image

from services.notifier import (
    Notifier,
    _escape_markdown_v2,
    _format_item_text,
    bold_telegram_md,
)


class TestEscapeMarkdownV2(unittest.TestCase):
    """Test the _escape_markdown_v2 helper function."""

    def test_escape_special_characters(self):
        """Test that MarkdownV2 special characters are escaped."""
        input_text = "Test *bold* _italic_ [link](url) `code`"
        result = _escape_markdown_v2(input_text)
        self.assertIn(r"\*bold\*", result)
        self.assertIn(r"\_italic\_", result)
        self.assertIn(r"\[link\]\(url\)", result)
        self.assertIn(r"\`code\`", result)

    def test_escape_all_special_chars(self):
        """Test escaping all MarkdownV2 special characters."""
        text = "_*[]()~`>#+-=|{}.!"
        result = _escape_markdown_v2(text)
        for char in text:
            self.assertIn(f"\\{char}", result)

    def test_escape_mixed_text(self):
        """Test escaping text with multiple special chars."""
        text = "Price: 1,500-2,000 (50m²) - Modern & Cozy! #1"
        result = _escape_markdown_v2(text)
        # These chars should be escaped in MarkdownV2
        self.assertIn(r"\-", result)  # hyphen
        self.assertIn(r"\(", result)  # parenthesis
        self.assertIn(r"\)", result)
        self.assertIn(r"\!", result)  # exclamation
        self.assertIn(r"\#", result)  # hash

    def test_escape_empty_string(self):
        """Test that empty string is handled correctly."""
        result = _escape_markdown_v2("")
        self.assertEqual(result, "")

    def test_escape_none(self):
        """Test that None is handled correctly."""
        result = _escape_markdown_v2(None)
        self.assertIsNone(result)

    def test_escape_regular_text(self):
        """Test that text without special chars is unchanged."""
        text = "This is normal text"
        result = _escape_markdown_v2(text)
        self.assertEqual(result, text)

    def test_escape_real_world_title(self):
        """Test escaping a real-world title with asterisk."""
        title = "*Luksusowy dom w urokliwej okolicy rzeki"
        result = _escape_markdown_v2(title)
        # Asterisk should be escaped
        self.assertIn(r"\*Luksusowy", result)
        # Other characters should remain
        self.assertIn("dom", result)


class TestBoldTelegramMd(unittest.TestCase):
    """Test the bold_telegram_md helper function."""

    def test_bold_simple_text(self):
        """Test bolding simple text."""
        result = bold_telegram_md("Hello World")
        self.assertEqual(result, "*Hello World*")

    def test_bold_text_with_asterisk(self):
        """Test bolding text that contains asterisks."""
        result = bold_telegram_md("*Luksusowy dom")
        # Asterisk is escaped, then wrapped in bold
        self.assertEqual(result, r"*\*Luksusowy dom*")

    def test_bold_text_with_multiple_asterisks(self):
        """Test bolding text with asterisks in middle and edges."""
        result = bold_telegram_md("*Price: 1000* PLN*")
        # Edge asterisks stripped, middle one escaped
        self.assertIn("Price:", result)
        self.assertTrue(result.startswith("*"))
        self.assertTrue(result.endswith("*"))

    def test_bold_empty_string(self):
        """Test bolding empty string."""
        result = bold_telegram_md("")
        self.assertEqual(result, "")

    def test_bold_none(self):
        """Test bolding None."""
        result = bold_telegram_md(None)
        self.assertEqual(result, "")


class TestNotifier(IsolatedAsyncioTestCase):
    async def test_format_item_text_variants(self):
        item_dict = {
            "title": "Nice flat",
            "price": "2000",
            "location": "Warsaw",
            "created_at_pretty": "today",
            "item_url": "http://x",
            "description": "price: 2000\ndeposit: 1000\nanimals_allowed: true\nrent: 300",
            "source": "olx",
        }
        text = _format_item_text(item_dict)
        self.assertIn("Nice flat", text)
        self.assertIn("Price:", text)
        self.assertIn("Deposit:", text)
        self.assertIn("Pets: Allowed", text)
        self.assertIn("Additional rent:", text)
        self.assertIn("View on olx", text)

    async def test_format_item_text_with_special_characters(self):
        """Test that special Markdown characters in item data are properly escaped."""
        item_dict = {
            "title": "*Luksusowy dom* w okolicy [rzeki]",
            "price": "1,500-2,000",
            "location": "Warsaw_Center",
            "created_at_pretty": "today 2h ago",  # No backticks - not escaped
            "item_url": "http://example.com",
            "description": "price: 1,800\ndeposit: 500",
            "source": "OLX.pl",
        }
        text = _format_item_text(item_dict)
        # Title should be wrapped in bold with escaped content
        self.assertIn("*", text)  # Bold markers present
        self.assertIn(r"\*Luksusowy", text)  # Asterisk escaped in title
        self.assertIn(r"\[rzeki\]", text)  # Brackets escaped in title
        # Location underscore is escaped
        self.assertIn(r"Warsaw\_Center", text)
        # MarkdownV2 structure maintained
        self.assertIn("📦 *", text)
        self.assertIn("💰 *Price*:", text)  # Bold Price, colon outside

        # Object-like access
        class Obj:
            title = "T"
            price = "P"
            location = "L"
            created_at_pretty = "C"
            item_url = "U"
            description = ""

        text2 = _format_item_text(Obj())
        self.assertIn("T", text2)
        self.assertIn("View on Unknown source", text2)

    async def test_check_and_send_items_none(self):
        bot = AsyncMock()
        svc = AsyncMock()
        redis_client = AsyncMock()
        svc.pending_tasks.return_value = [MagicMock(chat_id="1", name="n", id=7)]
        svc.items_to_send.return_value = []

        n = Notifier(bot, svc, redis_client)
        await n._check_and_send_items()

        svc.update_last_updated.assert_awaited()  # called for empty items
        svc.update_last_got_item.assert_not_called()
        bot.send_message.assert_not_awaited()

    async def test_check_and_send_items_with_items(self):
        bot = AsyncMock()
        svc = AsyncMock()
        redis_client = AsyncMock()
        redis_client.get.return_value = None  # No cached file_ids
        task = MagicMock(chat_id="1", name="n", id=7)
        items = [
            {
                "title": "A",
                "price": "1",
                "location": "L",
                "created_at_pretty": "C",
                "item_url": "U",
                "image_url": None,
            },
            {
                "title": "B",
                "price": "2",
                "location": "L",
                "created_at_pretty": "C",
                "item_url": "U",
                "image_url": "IMG",
            },
        ]
        svc.pending_tasks.return_value = [task]
        svc.items_to_send.return_value = items

        # Mock successful photo send response with file_id
        mock_message = AsyncMock()
        mock_message.photo = [MagicMock(file_id="cached_file_id_123")]
        bot.send_photo.return_value = mock_message

        n = Notifier(bot, svc, redis_client)
        with patch("asyncio.sleep", new=AsyncMock()) as _:
            await n._check_and_send_items()

        # First a caption photo notification
        bot.send_photo.assert_any_await(
            chat_id="1", photo=unittest.mock.ANY, caption=unittest.mock.ANY
        )
        # Then per-item messages/photos
        bot.send_message.assert_awaited()  # for item without image
        bot.send_photo.assert_awaited()  # for item with image
        svc.update_last_got_item.assert_awaited_with(7)
        svc.update_last_updated.assert_awaited_with(task)

    async def test_run_periodically_breaks(self):
        bot = AsyncMock()
        svc = AsyncMock()
        redis_client = AsyncMock()
        n = Notifier(bot, svc, redis_client)

        async def fake_sleep(_):
            raise asyncio.CancelledError

        with patch.object(n, "_check_and_send_items", new=AsyncMock()) as check:
            with patch("services.notifier.asyncio.sleep", new=fake_sleep):
                with self.assertRaises(asyncio.CancelledError):
                    await n.run_periodically(1)
        check.assert_awaited()


class TestImageCachingAndResizing(IsolatedAsyncioTestCase):
    """Test image caching and resizing functionality."""

    async def test_send_item_with_cached_file_id(self):
        """Test that cached file_id is used when available."""
        bot = AsyncMock()
        svc = AsyncMock()
        redis_client = AsyncMock()
        redis_client.get.return_value = b"cached_file_id_123"

        n = Notifier(bot, svc, redis_client)
        await n._send_item_with_image(
            chat_id=123, image_url="http://example.com/img.jpg", text="Test"
        )

        # Should use cached file_id
        redis_client.get.assert_awaited_with("photo:http://example.com/img.jpg")
        bot.send_photo.assert_awaited_once()
        # Verify it used the cached file_id
        call_args = bot.send_photo.call_args
        self.assertEqual(call_args.kwargs["photo"], b"cached_file_id_123")
        # Should not set new cache entry
        redis_client.set.assert_not_awaited()

    async def test_send_item_direct_url_success(self):
        """Test successful direct URL send and caching."""
        bot = AsyncMock()
        svc = AsyncMock()
        redis_client = AsyncMock()
        redis_client.get.return_value = None  # No cache

        # Mock successful photo send
        mock_message = AsyncMock()
        mock_message.photo = [MagicMock(file_id="new_file_id_456")]
        bot.send_photo.return_value = mock_message

        n = Notifier(bot, svc, redis_client)
        await n._send_item_with_image(
            chat_id=123, image_url="http://example.com/img.jpg", text="Test"
        )

        # Should try direct URL
        bot.send_photo.assert_awaited_once()
        call_args = bot.send_photo.call_args
        self.assertEqual(call_args.kwargs["photo"], "http://example.com/img.jpg")

        # Should cache the new file_id
        redis_client.set.assert_awaited_once()
        set_call = redis_client.set.call_args
        self.assertEqual(set_call.args[0], "photo:http://example.com/img.jpg")
        self.assertEqual(set_call.args[1], "new_file_id_456")
        self.assertIn("ex", set_call.kwargs)  # TTL set

    async def test_send_item_fallback_to_fetch_with_headers(self):
        """Test fallback to fetching with custom headers when direct URL fails."""
        bot = AsyncMock()
        svc = AsyncMock()
        redis_client = AsyncMock()
        redis_client.get.return_value = None

        # Mock direct URL failure, then success with fetched image
        from aiogram.exceptions import TelegramBadRequest

        bot.send_photo.side_effect = [
            TelegramBadRequest(method="sendPhoto", message="Bad Request"),
            AsyncMock(photo=[MagicMock(file_id="fetched_file_id_789")]),
        ]

        # Mock the fetch method to return valid image
        mock_buffered_file = MagicMock()
        with patch.object(
            Notifier, "_fetch_image_with_headers", return_value=mock_buffered_file
        ):
            n = Notifier(bot, svc, redis_client)
            await n._send_item_with_image(
                chat_id=123, image_url="http://example.com/img.jpg", text="Test"
            )

        # Should have tried twice: direct URL, then fetched
        self.assertEqual(bot.send_photo.await_count, 2)

        # Should cache the fetched file_id
        redis_client.set.assert_awaited_once()
        set_call = redis_client.set.call_args
        self.assertEqual(set_call.args[1], "fetched_file_id_789")

    async def test_send_item_fallback_to_text(self):
        """Test fallback to text message when all image methods fail."""
        bot = AsyncMock()
        svc = AsyncMock()
        redis_client = AsyncMock()
        redis_client.get.return_value = None

        # Mock all photo sends failing
        from aiogram.exceptions import TelegramBadRequest

        bot.send_photo.side_effect = TelegramBadRequest(
            method="sendPhoto", message="Bad Request"
        )

        # Mock fetch returning None (failed)
        with patch.object(Notifier, "_fetch_image_with_headers", return_value=None):
            n = Notifier(bot, svc, redis_client)
            await n._send_item_with_image(
                chat_id=123, image_url="http://example.com/img.jpg", text="Test message"
            )

        # Should have tried direct URL once
        bot.send_photo.assert_awaited_once()

        # Should fallback to text message
        bot.send_message.assert_awaited_once()
        call_args = bot.send_message.call_args
        self.assertEqual(call_args.kwargs["text"], "Test message")

    def test_resize_image_within_limits(self):
        """Test that images within Telegram limits are not resized."""
        bot = AsyncMock()
        svc = AsyncMock()
        redis_client = AsyncMock()
        n = Notifier(bot, svc, redis_client)

        # Create a small image (within limits)
        img = Image.new("RGB", (1000, 1000), color="red")
        output = BytesIO()
        img.save(output, format="JPEG")
        image_data = output.getvalue()

        # Should return original data
        result = n._resize_image_if_needed(image_data)
        self.assertEqual(result, image_data)

    def test_resize_image_exceeds_limits(self):
        """Test that oversized images are resized."""
        bot = AsyncMock()
        svc = AsyncMock()
        redis_client = AsyncMock()
        n = Notifier(bot, svc, redis_client)

        # Create an oversized image (4160x6240 = 10,400 > 10,000)
        img = Image.new("RGB", (4160, 6240), color="blue")
        output = BytesIO()
        img.save(output, format="JPEG")
        image_data = output.getvalue()

        # Should resize
        result = n._resize_image_if_needed(image_data)
        self.assertIsNotNone(result)
        self.assertNotEqual(result, image_data)  # Different from original

        # Check resized dimensions
        resized_img = Image.open(BytesIO(result))
        width, height = resized_img.size
        self.assertLessEqual(width + height, 10000)
        self.assertLessEqual(width, 10000)
        self.assertLessEqual(height, 10000)

        # Check aspect ratio preserved (approximately)
        original_ratio = 4160 / 6240
        resized_ratio = width / height
        self.assertAlmostEqual(original_ratio, resized_ratio, places=2)

    def test_resize_image_preserves_quality(self):
        """Test that resized images are valid JPEG."""
        bot = AsyncMock()
        svc = AsyncMock()
        redis_client = AsyncMock()
        n = Notifier(bot, svc, redis_client)

        # Create oversized image
        img = Image.new("RGB", (5000, 6000), color="green")
        output = BytesIO()
        img.save(output, format="JPEG")
        image_data = output.getvalue()

        # Resize
        result = n._resize_image_if_needed(image_data)

        # Should be valid JPEG
        resized_img = Image.open(BytesIO(result))
        self.assertEqual(resized_img.format, "JPEG")
        self.assertEqual(resized_img.mode, "RGB")

    def test_resize_image_handles_invalid_data(self):
        """Test that invalid image data is handled gracefully."""
        bot = AsyncMock()
        svc = AsyncMock()
        redis_client = AsyncMock()
        n = Notifier(bot, svc, redis_client)

        # Invalid image data
        invalid_data = b"not an image"

        # Should return None
        result = n._resize_image_if_needed(invalid_data)
        self.assertIsNone(result)

    async def test_cached_file_id_expired(self):
        """Test that expired cached file_id is removed and retried."""
        bot = AsyncMock()
        svc = AsyncMock()
        redis_client = AsyncMock()
        redis_client.get.return_value = b"expired_file_id"

        # Mock cached file_id failing, then direct URL succeeding
        from aiogram.exceptions import TelegramBadRequest

        mock_message = AsyncMock()
        mock_message.photo = [MagicMock(file_id="new_file_id")]
        bot.send_photo.side_effect = [
            TelegramBadRequest(method="sendPhoto", message="Bad Request"),
            mock_message,
        ]

        n = Notifier(bot, svc, redis_client)
        await n._send_item_with_image(
            chat_id=123, image_url="http://example.com/img.jpg", text="Test"
        )

        # Should delete expired cache
        redis_client.delete.assert_awaited_once_with("photo:http://example.com/img.jpg")

        # Should try again with direct URL and cache new file_id
        self.assertEqual(bot.send_photo.await_count, 2)
        redis_client.set.assert_awaited_once()
