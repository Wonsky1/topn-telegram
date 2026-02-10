"""Business-logic / use-case layer for monitoring.

Depends only on abstract *interfaces* (validator & repository), which
facilitates unit testing and adheres to the Dependency-Inversion
principle.  Telegram-specific concerns live in bot.handlers.* modules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from repositories.monitoring import MonitoringRepositoryProtocol
from services.validator import UrlValidatorProtocol

logger = logging.getLogger(__name__)

__all__ = [
    "MonitoringSpec",
    "MonitoringService",
]


@dataclass(frozen=True, slots=True)
class MonitoringSpec:
    """Value-object containing validated monitoring parameters."""

    chat_id: str
    name: str
    url: str  # *canonical* URL produced by UrlValidator.normalize()
    city_id: int | None = None  # Optional city ID for location filtering
    allowed_district_ids: list[int] | None = None  # Optional district filter


class MonitoringService:  # noqa: D101 – simple name
    def __init__(
        self,
        repo: MonitoringRepositoryProtocol,
        validator: UrlValidatorProtocol,
    ) -> None:
        self._repo = repo
        self._validator = validator

    # ---------------- Public API used by Telegram handlers ----------------
    async def add_monitoring(self, spec: MonitoringSpec) -> None:
        """Validate and persist a new monitoring task.

        Raises ValueError with descriptive message if validation fails so that
        the caller (Telegram handler) can translate it into user-friendly
        messages.
        """
        name = spec.name.strip()
        if not name or len(name) > 64:
            raise ValueError("Name must be between 1 and 64 characters long.")
        if name.startswith("/"):
            raise ValueError("Name may not start with '/'.")

        url = spec.url.strip()
        if not self._validator.is_supported(url):
            raise ValueError("Unsupported URL.")
        url = self._validator.normalize(url)
        if not await self._validator.is_reachable(url):
            raise ValueError("URL not reachable.")
        # Check duplicates
        if await self._repo.has_url(spec.chat_id, url):
            raise ValueError("Duplicate URL for this chat.")
        if await self._repo.task_exists(spec.chat_id, name):
            raise ValueError("Duplicate name for this chat.")
        # Everything OK → persist
        await self._repo.create_task(
            chat_id=spec.chat_id,
            name=name,
            url=url,
            city_id=spec.city_id,
            allowed_district_ids=spec.allowed_district_ids,
        )
        logger.info("Monitoring '%s' created for chat_id %s", name, spec.chat_id)

    async def remove_monitoring(self, chat_id: str, name: str) -> None:
        """Delete monitoring task.

        Raises ValueError if it does not exist so that UI can respond.
        """
        if not await self._repo.task_exists(chat_id, name):
            raise ValueError("Monitoring not found.")
        await self._repo.delete_task(chat_id, name)
        logger.info("Monitoring '%s' deleted for chat_id %s", name, chat_id)

    async def list_monitorings(self, chat_id: str):  # -> Sequence[MonitoringTask]
        return await self._repo.list_tasks(chat_id)

    # ---------------- Background-worker helpers (pass-through) ----------------
    async def pending_tasks(self):
        return await self._repo.pending_tasks()

    async def items_to_send(self, task):
        return await self._repo.items_to_send(task)

    async def update_last_got_item(self, chat_id: str) -> None:
        await self._repo.update_last_got_item(chat_id)

    async def update_last_updated(self, task) -> None:
        await self._repo.update_last_updated(task)
