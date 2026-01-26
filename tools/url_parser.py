"""URL parsing utilities for extracting location information from OLX URLs."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

from unidecode import unidecode


def normalize_city_name(name: str) -> str:
    """Normalize city name for database lookup.

    Converts to lowercase and removes diacritics using unidecode.

    Args:
        name: Raw city name (e.g., "Warszawa", "Kraków")

    Returns:
        Normalized name (e.g., "warszawa", "krakow")
    """
    return unidecode(name).lower().strip()


def extract_city_from_olx_url(url: str) -> Optional[str]:
    """Extract city slug from OLX URL.

    Parses OLX URLs to find the city segment in the path.
    Returns the normalized city name ready for database lookup.

    Args:
        url: OLX URL (e.g., "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/warszawa/")

    Returns:
        Normalized city name or None if not found

    Examples:
        >>> extract_city_from_olx_url("https://www.olx.pl/nieruchomosci/mieszkania/wynajem/warszawa/")
        "warszawa"
        >>> extract_city_from_olx_url("https://www.olx.pl/d/nieruchomosci/mieszkania/wynajem/krakow/")
        "krakow"
        >>> extract_city_from_olx_url("https://www.olx.pl/nieruchomosci/mieszkania/")
        None
    """
    try:
        # Validate URL format - must be OLX URL
        if not url or not url.startswith(("http://", "https://")):
            return None

        parsed = urlparse(url)

        # Must be olx.pl domain
        if "olx.pl" not in parsed.netloc.lower():
            return None

        path = parsed.path.strip("/")
        if not path:
            return None

        segments = path.split("/")

        # OLX URL patterns:
        # /nieruchomosci/mieszkania/wynajem/warszawa/
        # /d/nieruchomosci/mieszkania/wynajem/krakow/
        # /nieruchomosci/mieszkania/wynajem/warszawa/?search[...]

        # Known category segments that are NOT cities
        non_city_segments = {
            "nieruchomosci",
            "mieszkania",
            "wynajem",
            "sprzedaz",
            "domy",
            "dzialki",
            "pokoje",
            "stancje",
            "d",  # alternative path prefix
            "oferty",
            "praca",
            "motoryzacja",
            "elektronika",
            "dom-ogrod",
            "moda",
            "rolnictwo",
        }

        # Find the city segment - it's typically the last meaningful segment
        # that is not a known category
        for segment in reversed(segments):
            if not segment:
                continue
            # Skip known non-city segments
            if segment.lower() in non_city_segments:
                continue
            # Skip segments that look like IDs or query params
            if segment.isdigit():
                continue
            # Skip segments with special characters (likely not a city)
            if re.search(r"[?&=]", segment):
                continue

            # This is likely the city slug
            return normalize_city_name(segment)

        return None

    except Exception:
        return None


def is_city_in_url(url: str) -> bool:
    """Check if URL contains a city segment.

    Args:
        url: OLX URL to check

    Returns:
        True if city was found in URL
    """
    return extract_city_from_olx_url(url) is not None
