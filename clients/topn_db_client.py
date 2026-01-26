from logging import getLogger
from typing import Any, Dict, Optional

import httpx

logger = getLogger(__name__)


class TopnDbClient:
    """Client for communicating with the OLX Database API."""

    def __init__(self, base_url: str, client: Optional[httpx.AsyncClient] = None):
        """Initialize the database client.

        Args:
            base_url: Base URL of the database API
            client: Optional httpx.AsyncClient instance. If not provided, a new one will be created.
        """
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.AsyncClient()
        self._own_client = client is None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._own_client:
            await self.client.aclose()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            json_data: JSON data to send in request body
            params: Query parameters

        Returns:
            Response data as dictionary

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        url = f"{self.base_url}{endpoint}"

        logger.debug(f"Making {method} request to {url}")

        try:
            response = await self.client.request(
                method=method, url=url, json=json_data, params=params
            )
            response.raise_for_status()

            # Handle 204 No Content responses
            if response.status_code == 204:
                return {"success": True}

            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error {e.response.status_code} for {method} {url}: {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Request failed for {method} {url}: {str(e)}")
            raise

    # ==================== API Root & Health ====================

    async def get_api_root(self) -> Dict[str, Any]:
        """Get API root information."""
        return await self._make_request("GET", "/")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        return await self._make_request("GET", "/health")

    # ==================== Monitoring Tasks ====================

    async def get_all_tasks(self) -> Dict[str, Any]:
        """Get all monitoring tasks."""
        return await self._make_request("GET", "/api/v1/tasks/")

    async def get_tasks_by_chat_id(self, chat_id: str) -> Dict[str, Any]:
        """Get tasks by chat ID."""
        return await self._make_request("GET", f"/api/v1/tasks/chat/{chat_id}")

    async def get_task_by_id(self, task_id: int) -> Dict[str, Any]:
        """Get task by ID."""
        return await self._make_request("GET", f"/api/v1/tasks/{task_id}")

    async def create_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new monitoring task."""
        return await self._make_request("POST", "/api/v1/tasks/", json_data=task_data)

    async def update_task(
        self, task_id: int, task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing monitoring task."""
        return await self._make_request(
            "PUT", f"/api/v1/tasks/{task_id}", json_data=task_data
        )

    async def delete_task_by_id(self, task_id: int) -> Dict[str, Any]:
        """Delete monitoring task by ID."""
        return await self._make_request("DELETE", f"/api/v1/tasks/{task_id}")

    async def delete_tasks_by_chat_id(
        self, chat_id: str, name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete tasks by chat ID, optionally filtering by name."""
        params = {"name": name} if name else None
        return await self._make_request(
            "DELETE", f"/api/v1/tasks/chat/{chat_id}", params=params
        )

    async def get_pending_tasks(self) -> Dict[str, Any]:
        """Get pending tasks ready for processing."""
        return await self._make_request("GET", "/api/v1/tasks/pending")

    async def update_last_got_item_timestamp(self, task_id: int) -> Dict[str, Any]:
        """Update the last_got_item timestamp for a task."""
        return await self._make_request(
            "POST", f"/api/v1/tasks/{task_id}/update-last-got-item"
        )

    async def get_items_to_send_for_task(self, task_id: int) -> Dict[str, Any]:
        """Get items to send for a specific monitoring task."""
        return await self._make_request("GET", f"/api/v1/tasks/{task_id}/items-to-send")

    # ==================== Item Records ====================

    async def get_all_items(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """Get all items with pagination."""
        params = {"skip": skip, "limit": limit}
        return await self._make_request("GET", "/api/v1/items/", params=params)

    async def get_items_by_source_url(
        self, source_url: str, limit: int = 100
    ) -> Dict[str, Any]:
        """Get items filtered by source URL."""
        params = {"source_url": source_url, "limit": limit}
        return await self._make_request("GET", "/api/v1/items/by-source", params=params)

    async def get_recent_items(
        self, hours: int = 24, limit: int = 100
    ) -> Dict[str, Any]:
        """Get recent items from the last N hours."""
        params = {"hours": hours, "limit": limit}
        return await self._make_request("GET", "/api/v1/items/recent", params=params)

    async def get_item_by_id(self, item_id: int) -> Dict[str, Any]:
        """Get item by ID."""
        return await self._make_request("GET", f"/api/v1/items/{item_id}")

    async def get_item_by_url(self, item_url: str) -> Dict[str, Any]:
        """Get item by URL."""
        return await self._make_request("GET", f"/api/v1/items/by-url/{item_url}")

    async def create_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new item record."""
        return await self._make_request("POST", "/api/v1/items/", json_data=item_data)

    async def delete_item_by_id(self, item_id: int) -> Dict[str, Any]:
        """Delete item by ID."""
        return await self._make_request("DELETE", f"/api/v1/items/{item_id}")

    async def delete_old_items(self, days: int) -> Dict[str, Any]:
        """Delete items older than N days."""
        return await self._make_request(
            "DELETE", f"/api/v1/items/cleanup/older-than/{days}"
        )

    # ==================== Cities ====================

    async def get_all_cities(self) -> Dict[str, Any]:
        """Get all cities."""
        return await self._make_request("GET", "/api/v1/cities/")

    async def get_city_by_id(self, city_id: int) -> Dict[str, Any]:
        """Get city by ID."""
        return await self._make_request("GET", f"/api/v1/cities/{city_id}")

    async def get_city_by_normalized_name(
        self, name_normalized: str
    ) -> Optional[Dict[str, Any]]:
        """Get city by normalized name.

        Returns None if city not found (404).
        """
        try:
            return await self._make_request(
                "GET", f"/api/v1/cities/by-name/{name_normalized}"
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def get_city_with_districts(self, city_id: int) -> Dict[str, Any]:
        """Get city with all its districts."""
        return await self._make_request(
            "GET", f"/api/v1/cities/{city_id}/with-districts"
        )

    # ==================== Districts ====================

    async def get_all_districts(self) -> Dict[str, Any]:
        """Get all districts."""
        return await self._make_request("GET", "/api/v1/districts/")

    async def get_district_by_id(self, district_id: int) -> Dict[str, Any]:
        """Get district by ID."""
        return await self._make_request("GET", f"/api/v1/districts/{district_id}")

    async def get_districts_by_city_id(self, city_id: int) -> Dict[str, Any]:
        """Get all districts for a specific city."""
        return await self._make_request("GET", f"/api/v1/cities/{city_id}/districts")

    # ==================== Legacy Methods ====================

    async def add_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy method - use create_item instead."""
        logger.warning("add_item is deprecated, use create_item instead")
        return await self.create_item(item_data)
