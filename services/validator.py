"""URL validation and normalization utilities.

Single Responsibility: only handles URL-related concerns.
"""

from __future__ import annotations

import urllib.parse
from typing import Protocol

from tools.texts import is_valid_and_accessible

__all__ = [
    "UrlValidatorProtocol",
    "UrlValidator",
]


class UrlValidatorProtocol(Protocol):
    """Interface for URL validation utilities."""

    def is_supported(self, url: str) -> bool:  # noqa: D401 – simple name
        """Return True if the URL belongs to a supported domain/format."""

    def normalize(self, url: str) -> str:
        """Return canonical version of the supported URL."""

    async def is_reachable(self, url: str) -> bool:
        """Return True if remote host returns 2xx."""


class UrlValidator(UrlValidatorProtocol):
    """Validator/normaliser for OLX URLs."""

    _OLX_PREFIXES: tuple[str, ...] = (
        "https://olx.pl/",
        "https://www.olx.pl/",
        "https://m.olx.pl/",
        "https://www.m.olx.pl/",
    )

    def is_supported(self, url: str) -> bool:
        return url.startswith(self._OLX_PREFIXES)

    def normalize(self, url: str) -> str:
        """Convert any supported variant to https://www.olx.pl/... and sort query parameters.

        Also automatically sets search[order] to created_at:desc (newest first) regardless
        of the original sorting parameter in the URL.
        """
        if url.startswith("https://m.olx.pl/"):
            url = "https://www.olx.pl/" + url[len("https://m.olx.pl/") :]
        elif url.startswith("https://www.m.olx.pl/"):
            url = "https://www.olx.pl/" + url[len("https://www.m.olx.pl/") :]
        elif url.startswith("https://olx.pl/"):
            url = "https://www.olx.pl/" + url[len("https://olx.pl/") :]

        parsed = urllib.parse.urlparse(url)
        if parsed.query:
            qsl = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)

            # Force sorting to be newest first (created_at:desc)
            # Remove any existing search[order] parameter
            qsl = [(k, v) for k, v in qsl if k != "search[order]"]
            # Add the search[order]=created_at:desc parameter
            qsl.append(("search[order]", "created_at:desc"))

            qsl.sort()
            query = urllib.parse.urlencode(qsl, doseq=True)
            url = urllib.parse.urlunparse(parsed._replace(query=query))
        return url

    async def is_reachable(self, url: str) -> bool:  # noqa: D401 – simple name
        return await is_valid_and_accessible(url)
