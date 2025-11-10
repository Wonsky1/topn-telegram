from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from services.validator import UrlValidator


class TestUrlValidator(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.validator = UrlValidator()

    async def asyncTearDown(self):
        pass

    async def test_is_supported(self):
        self.assertTrue(self.validator.is_supported("https://olx.pl/abc"))
        self.assertTrue(self.validator.is_supported("https://www.olx.pl/abc"))
        self.assertTrue(self.validator.is_supported("https://m.olx.pl/abc"))
        self.assertFalse(self.validator.is_supported("https://example.com"))

    async def test_normalize_variants(self):
        # URL with query params should get search[order]=created_at:desc added
        self.assertEqual(
            self.validator.normalize("https://olx.pl/abc?b=2&a=1"),
            "https://www.olx.pl/abc?a=1&b=2&search%5Border%5D=created_at%3Adesc",
        )
        # URL without query params should remain unchanged
        self.assertEqual(
            self.validator.normalize("https://m.olx.pl/path/"),
            "https://www.olx.pl/path/",
        )
        self.assertEqual(
            self.validator.normalize("https://www.m.olx.pl/path/"),
            "https://www.olx.pl/path/",
        )

    async def test_normalize_replaces_sorting_parameter(self):
        """Test that any existing search[order] parameter is replaced with created_at:desc."""
        # Test with relevance sorting
        self.assertEqual(
            self.validator.normalize(
                "https://www.olx.pl/nieruchomosci/domy/sprzedaz/warszawa/"
                "?search%5Bdist%5D=30&search%5Border%5D=relevance:desc&search%5Bfilter_float_price:to%5D=1000000"
            ),
            "https://www.olx.pl/nieruchomosci/domy/sprzedaz/warszawa/"
            "?search%5Bdist%5D=30&search%5Bfilter_float_price%3Ato%5D=1000000&search%5Border%5D=created_at%3Adesc",
        )
        # Test with price ascending sorting
        self.assertEqual(
            self.validator.normalize(
                "https://www.olx.pl/nieruchomosci/domy/sprzedaz/warszawa/"
                "?search%5Bdist%5D=30&search%5Border%5D=filter_float_price:asc&search%5Bfilter_float_price:to%5D=1000000"
            ),
            "https://www.olx.pl/nieruchomosci/domy/sprzedaz/warszawa/"
            "?search%5Bdist%5D=30&search%5Bfilter_float_price%3Ato%5D=1000000&search%5Border%5D=created_at%3Adesc",
        )
        # Test with price descending sorting
        self.assertEqual(
            self.validator.normalize(
                "https://www.olx.pl/nieruchomosci/domy/sprzedaz/warszawa/"
                "?search%5Bdist%5D=30&search%5Border%5D=filter_float_price:desc&search%5Bfilter_float_price:to%5D=1000000"
            ),
            "https://www.olx.pl/nieruchomosci/domy/sprzedaz/warszawa/"
            "?search%5Bdist%5D=30&search%5Bfilter_float_price%3Ato%5D=1000000&search%5Border%5D=created_at%3Adesc",
        )
        # Test that created_at:desc is preserved (idempotent)
        self.assertEqual(
            self.validator.normalize(
                "https://www.olx.pl/nieruchomosci/domy/sprzedaz/warszawa/"
                "?search%5Bdist%5D=30&search%5Border%5D=created_at:desc&search%5Bfilter_float_price:to%5D=1000000"
            ),
            "https://www.olx.pl/nieruchomosci/domy/sprzedaz/warszawa/"
            "?search%5Bdist%5D=30&search%5Bfilter_float_price%3Ato%5D=1000000&search%5Border%5D=created_at%3Adesc",
        )

    @patch("services.validator.is_valid_and_accessible", new_callable=AsyncMock)
    async def test_is_reachable_true(self, mock_check):
        mock_check.return_value = True
        self.assertTrue(await self.validator.is_reachable("https://www.olx.pl/x"))

    @patch("services.validator.is_valid_and_accessible", new_callable=AsyncMock)
    async def test_is_reachable_false(self, mock_check):
        mock_check.return_value = False
        self.assertFalse(await self.validator.is_reachable("https://www.olx.pl/x"))
