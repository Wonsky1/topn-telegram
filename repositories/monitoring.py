"""Persistence layer for monitoring tasks.

Uses the TopnDbClient to communicate with the OLX Database API instead of
direct database connections. This provides better separation of concerns
and makes the codebase more maintainable.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Iterable, Protocol, Sequence

from clients import topn_db_client
from clients.topn_db_client import TopnDbClient
from tools.datetime_utils import now_warsaw

__all__ = [
    "MonitoringRepositoryProtocol",
    "MonitoringRepository",
]

SECOND = 1
MINUTE = 60 * SECOND
HOUR = 60 * MINUTE
DAY = 24 * HOUR


class MonitoringRepositoryProtocol(Protocol):
    """Abstract interface for monitoring persistence."""

    # --- CRUD & queries used by the bot ---
    async def task_exists(
        self, chat_id: str, name: str
    ) -> bool:  # noqa: D401 – simple name
        """Return True if a task with *name* exists for *chat_id*."""

    async def has_url(self, chat_id: str, url: str) -> bool:  # noqa: D401
        """Return True if the *url* is already monitored for *chat_id*."""

    async def create_task(
        self,
        chat_id: str,
        name: str,
        url: str,
        city_id: int | None = None,
        allowed_district_ids: list[int] | None = None,
    ) -> MonitoringTask:  # noqa: D401
        """Persist a new monitoring task and return the model instance."""

    async def delete_task(self, chat_id: str, name: str) -> None:
        """Delete monitoring task identified by *name* for the given chat."""

    async def list_tasks(self, chat_id: str) -> Sequence[MonitoringTask]:  # noqa: D401
        """Return all monitoring tasks for *chat_id*."""

    # --- Used by background worker ---
    async def pending_tasks(self) -> Iterable[MonitoringTask]:  # noqa: D401
        """Return tasks that need to be checked for new items."""

    async def items_to_send(self, task: MonitoringTask):  # noqa: D401
        """Return new items that should be sent for *task*."""

    async def update_last_got_item(self, chat_id: str) -> None:  # noqa: D401
        """Update `last_got_item` timestamp after sending items."""

    async def update_last_updated(self, task: MonitoringTask) -> None:  # noqa: D401
        """Update `last_updated` timestamp after checking for items."""


# Simple data class to represent MonitoringTask since we're moving away from ORM
class MonitoringTask:
    """Represents a monitoring task."""

    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.chat_id = data.get("chat_id")
        self.name = data.get("name")
        self.url = data.get("url")
        self.last_updated = data.get("last_updated")
        self.last_got_item = data.get("last_got_item")
        self.created_at = data.get("created_at")
        self.is_active = data.get("is_active", True)

    @staticmethod
    async def has_url_for_chat(client: TopnDbClient, chat_id: str, url: str) -> bool:
        """Check if URL is already monitored for the given chat."""
        try:
            tasks_response = await client.get_tasks_by_chat_id(chat_id)
            tasks = tasks_response.get("tasks", [])
            return any(task.get("url") == url for task in tasks)
        except Exception:
            return False


class MonitoringRepository(MonitoringRepositoryProtocol):
    """Client-backed implementation using TopnDbClient for API communication."""

    def __init__(self, client: TopnDbClient = None):
        self._client = client or topn_db_client
        self._logger = logging.getLogger(__name__)

    # ----------------- CRUD wrappers -----------------
    async def task_exists(self, chat_id: str, name: str) -> bool:  # noqa: D401
        """Return True if a task with *name* exists for *chat_id*."""
        try:
            tasks_response = await self._client.get_tasks_by_chat_id(chat_id)
            tasks = tasks_response.get("tasks", [])
            return any(task.get("name") == name for task in tasks)
        except Exception as e:
            self._logger.error(f"Error checking if task exists: {e}")
            return False

    async def has_url(self, chat_id: str, url: str) -> bool:  # noqa: D401
        """Return True if the *url* is already monitored for *chat_id*."""
        return await MonitoringTask.has_url_for_chat(self._client, chat_id, url)

    async def create_task(
        self,
        chat_id: str,
        name: str,
        url: str,
        city_id: int | None = None,
        allowed_district_ids: list[int] | None = None,
    ) -> MonitoringTask:  # noqa: D401
        """Persist a new monitoring task and return the model instance."""
        task_data = {
            "chat_id": chat_id,
            "name": name,
            "url": url,
        }

        # Add optional location filtering
        if city_id is not None:
            task_data["city_id"] = city_id
        if allowed_district_ids:
            task_data["allowed_district_ids"] = allowed_district_ids

        try:
            response = await self._client.create_task(task_data)
            return MonitoringTask(response.get("task", response))
        except Exception as e:
            self._logger.error(f"Error creating task: {e}")
            raise

    async def delete_task(self, chat_id: str, name: str) -> None:
        """Delete monitoring task identified by *name* for the given chat."""
        try:
            await self._client.delete_tasks_by_chat_id(chat_id, name)
        except Exception as e:
            self._logger.error(f"Error deleting task: {e}")
            raise

    async def list_tasks(self, chat_id: str) -> Sequence[MonitoringTask]:  # noqa: D401
        """Return all monitoring tasks for *chat_id*."""
        try:
            response = await self._client.get_tasks_by_chat_id(chat_id)
            tasks_data = response.get("tasks", [])
            return [MonitoringTask(task_data) for task_data in tasks_data]
        except Exception as e:
            self._logger.error(f"Error listing tasks: {e}")
            return []

    # ----------------- Background / worker helpers -----------------
    async def pending_tasks(self) -> Iterable[MonitoringTask]:  # noqa: D401
        """Return tasks that need to be checked for new items."""
        try:
            response = await self._client.get_pending_tasks()
            tasks_data = response.get("tasks", [])
            return [MonitoringTask(task_data) for task_data in tasks_data]
        except Exception as e:
            self._logger.error(f"Error getting pending tasks: {e}")
            return []

    async def items_to_send(self, task: MonitoringTask):  # noqa: D401
        """Return new items that should be sent for *task*."""
        try:
            response = await self._client.get_items_to_send_for_task(task.id)
            return response.get("items", [])
        except Exception as e:
            self._logger.error(f"Error getting items to send: {e}")
            return []

    async def update_last_got_item(self, chat_id: str) -> None:  # noqa: D401
        """Update `last_got_item` timestamp after sending items."""
        try:
            # Find the task by chat_id first, then update
            tasks = await self.list_tasks(chat_id)
            for task in tasks:
                await self._client.update_last_got_item_timestamp(task.id)
        except Exception as e:
            self._logger.error(f"Error updating last_got_item: {e}")

    async def update_last_updated(self, task: MonitoringTask) -> None:  # noqa: D401
        """Update `last_updated` timestamp after checking for items."""
        try:
            # Update the task with current timestamp
            task_data = {"last_updated": now_warsaw().isoformat()}
            await self._client.update_task(task.id, task_data)
        except Exception as e:
            self._logger.error(f"Error updating last_updated: {e}")

    async def remove_old_items_data_infinitely(self, n_days: int) -> None:
        """Remove old items data in an infinite loop."""
        while True:
            try:
                await self._client.delete_old_items(n_days)
                self._logger.info(f"Cleaned up items older than {n_days} days")
            except Exception as e:
                self._logger.error(f"Error cleaning up old items: {e}")
            await asyncio.sleep(DAY)
