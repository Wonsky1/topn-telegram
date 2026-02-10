"""Tests for URL parsing utilities."""

from tools.url_parser import (
    extract_city_from_olx_url,
    is_city_in_url,
    normalize_city_name,
)


class TestNormalizeCityName:
    """Tests for normalize_city_name function."""

    def test_lowercase(self):
        assert normalize_city_name("Warszawa") == "warszawa"
        assert normalize_city_name("KRAKÓW") == "krakow"

    def test_removes_diacritics(self):
        assert normalize_city_name("Kraków") == "krakow"
        assert normalize_city_name("Łódź") == "lodz"
        assert normalize_city_name("Gdańsk") == "gdansk"
        assert normalize_city_name("Wrocław") == "wroclaw"

    def test_strips_whitespace(self):
        assert normalize_city_name("  Warszawa  ") == "warszawa"
        assert normalize_city_name("\tKraków\n") == "krakow"


class TestExtractCityFromOlxUrl:
    """Tests for extract_city_from_olx_url function."""

    def test_basic_url(self):
        url = "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/warszawa/"
        assert extract_city_from_olx_url(url) == "warszawa"

    def test_url_with_query_params(self):
        url = "https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/warszawa/?search%5Bfilter_enum_furniture%5D=yes"
        assert extract_city_from_olx_url(url) == "warszawa"

    def test_url_with_d_prefix(self):
        url = "https://www.olx.pl/d/nieruchomosci/mieszkania/wynajem/krakow/"
        assert extract_city_from_olx_url(url) == "krakow"

    def test_url_with_polish_city(self):
        url = "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/lodz/"
        assert extract_city_from_olx_url(url) == "lodz"

    def test_url_without_city(self):
        url = "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/"
        assert extract_city_from_olx_url(url) is None

    def test_url_only_categories(self):
        url = "https://www.olx.pl/nieruchomosci/"
        assert extract_city_from_olx_url(url) is None

    def test_different_categories(self):
        # sprzedaz (sale) instead of wynajem (rent)
        url = "https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/gdansk/"
        assert extract_city_from_olx_url(url) == "gdansk"

    def test_invalid_url(self):
        assert extract_city_from_olx_url("not a url") is None
        assert extract_city_from_olx_url("") is None

    def test_url_with_numeric_segment(self):
        # Numeric segments should be skipped
        url = "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/warszawa/12345/"
        # Should still find warszawa, not 12345
        result = extract_city_from_olx_url(url)
        assert result is not None


class TestIsCityInUrl:
    """Tests for is_city_in_url function."""

    def test_url_with_city(self):
        url = "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/warszawa/"
        assert is_city_in_url(url) is True

    def test_url_without_city(self):
        url = "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/"
        assert is_city_in_url(url) is False

    def test_invalid_url(self):
        assert is_city_in_url("not a url") is False
