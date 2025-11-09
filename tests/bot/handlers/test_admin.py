"""Tests for admin panel handlers."""

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import types


class TestAdminKeyboards(IsolatedAsyncioTestCase):
    """Test admin panel keyboard structures."""

    async def test_get_admin_panel_keyboard_structure(self):
        from bot.keyboards import get_admin_panel_keyboard

        kb = get_admin_panel_keyboard()
        self.assertIsInstance(kb, types.ReplyKeyboardMarkup)
        rows = kb.keyboard
        # Should have 3 rows: [System Status, View Users], [View All Tasks, Recent Errors], [Back to Menu]
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rows[0]), 2)
        self.assertEqual(rows[0][0].text, "📊 System Status")
        self.assertEqual(rows[0][1].text, "👥 View Users")
        self.assertEqual(len(rows[1]), 2)
        self.assertEqual(rows[1][0].text, "📋 View All Tasks")
        self.assertEqual(rows[1][1].text, "⚠️ Recent Errors")
        self.assertEqual(len(rows[2]), 1)
        self.assertEqual(rows[2][0].text, "⬅️ Back to Menu")
        self.assertTrue(kb.resize_keyboard)


class TestAdminHandlers(IsolatedAsyncioTestCase):
    """Test admin panel handlers."""

    def setUp(self):
        from bot.handlers import admin as ahandlers

        self.ahandlers = ahandlers

        # Common mocks
        self.message = MagicMock()
        self.message.chat = MagicMock(id=123456)
        self.message.answer = AsyncMock()
        self.state = MagicMock()
        self.state.clear = AsyncMock()

    async def test_is_admin_helper(self):
        """Test the is_admin helper function."""
        with patch("bot.handlers.admin.settings") as mock_settings:
            mock_settings.is_admin.return_value = True
            result = self.ahandlers.is_admin(123456)
            self.assertTrue(result)
            mock_settings.is_admin.assert_called_once_with(123456)

            mock_settings.is_admin.return_value = False
            result = self.ahandlers.is_admin(999999)
            self.assertFalse(result)

    async def test_admin_panel_menu_access_granted(self):
        """Test admin panel menu shows for admin users."""
        with patch.object(self.ahandlers, "is_admin", return_value=True):
            await self.ahandlers.admin_panel_menu(self.message, self.state)
            self.state.clear.assert_awaited_once()
            self.message.answer.assert_awaited_once()
            call_args = self.message.answer.await_args
            self.assertIn("Admin Panel", call_args[0][0])
            self.assertIn("reply_markup", call_args[1])

    async def test_admin_panel_menu_access_denied(self):
        """Test admin panel menu denies non-admin users."""
        with patch.object(self.ahandlers, "is_admin", return_value=False):
            await self.ahandlers.admin_panel_menu(self.message, self.state)
            self.message.answer.assert_awaited_once()
            call_args = self.message.answer.await_args
            self.assertIn("Access denied", call_args[0][0])

    async def test_system_status_access_denied(self):
        """Test system status denies non-admin users."""
        with patch.object(self.ahandlers, "is_admin", return_value=False):
            await self.ahandlers.system_status(self.message, self.state)
            self.message.answer.assert_awaited_once()
            call_args = self.message.answer.await_args
            self.assertIn("Access denied", call_args[0][0])

    async def test_system_status_success(self):
        """Test system status displays correctly for admin users."""
        with patch.object(self.ahandlers, "is_admin", return_value=True), patch.object(
            self.ahandlers, "get_monitoring_service"
        ) as mock_svc, patch.object(
            self.ahandlers, "get_repository"
        ) as mock_repo, patch(
            "bot.handlers.admin.psutil"
        ) as mock_psutil:

            # Mock repository responses
            mock_client = MagicMock()
            mock_repo.return_value._client = mock_client
            mock_client.get_all_tasks = AsyncMock(
                return_value={
                    "tasks": [
                        {"chat_id": "123", "is_active": True},
                        {"chat_id": "456", "is_active": True},
                        {"chat_id": "123", "is_active": False},
                    ]
                }
            )
            mock_client.get_pending_tasks = AsyncMock(
                return_value={"tasks": [{"id": 1}]}
            )
            mock_client.health_check = AsyncMock(return_value={"status": "ok"})

            # Mock psutil
            mock_memory = MagicMock()
            mock_memory.used = 2 * (1024**3)  # 2GB
            mock_memory.total = 16 * (1024**3)  # 16GB
            mock_memory.percent = 12.5
            mock_psutil.virtual_memory.return_value = mock_memory

            mock_disk = MagicMock()
            mock_disk.used = 100 * (1024**3)  # 100GB
            mock_disk.total = 500 * (1024**3)  # 500GB
            mock_disk.percent = 20.0
            mock_psutil.disk_usage.return_value = mock_disk
            mock_psutil.cpu_percent.return_value = 15.5

            # Mock redis
            with patch("bot.handlers.admin.redis_client") as mock_redis:
                mock_redis.ping = AsyncMock()
                mock_redis.dbsize = AsyncMock(return_value=100)
                mock_redis.keys = AsyncMock(return_value=["photo:1", "photo:2"])

                await self.ahandlers.system_status(self.message, self.state)

                # Should have called answer twice (loading + status)
                self.assertEqual(self.message.answer.await_count, 2)

                # Check the final status message
                final_call = self.message.answer.await_args_list[1]
                status_text = final_call[0][0]

                self.assertIn("System Status", status_text)
                self.assertIn("Running", status_text)
                self.assertIn("Users:", status_text)
                self.assertIn("Total Tasks:", status_text)
                self.assertIn("CPU Usage:", status_text)
                self.assertIn("Memory:", status_text)
                self.assertIn("Disk:", status_text)

    async def test_system_status_handles_errors(self):
        """Test system status handles errors gracefully."""
        with patch.object(self.ahandlers, "is_admin", return_value=True), patch.object(
            self.ahandlers, "get_repository"
        ) as mock_repo:

            # Make repository raise an exception
            mock_repo.side_effect = Exception("Database connection failed")

            await self.ahandlers.system_status(self.message, self.state)

            # Should show error message
            self.assertTrue(self.message.answer.await_count >= 1)
            final_call = self.message.answer.await_args
            self.assertIn("Error", final_call[0][0])

    async def test_view_all_users_access_denied(self):
        """Test view all users denies non-admin users."""
        with patch.object(self.ahandlers, "is_admin", return_value=False):
            await self.ahandlers.view_all_users(self.message, self.state)
            self.message.answer.assert_awaited_once()
            call_args = self.message.answer.await_args
            self.assertIn("Access denied", call_args[0][0])

    async def test_view_all_users_success(self):
        """Test view all users displays user list."""
        with patch.object(self.ahandlers, "is_admin", return_value=True), patch.object(
            self.ahandlers, "get_repository"
        ) as mock_repo:

            mock_client = MagicMock()
            mock_repo.return_value._client = mock_client
            mock_client.get_all_tasks = AsyncMock(
                return_value={
                    "tasks": [
                        {"chat_id": "123", "name": "Task1", "is_active": True},
                        {"chat_id": "123", "name": "Task2", "is_active": True},
                        {"chat_id": "456", "name": "Task3", "is_active": False},
                    ]
                }
            )

            await self.ahandlers.view_all_users(self.message, self.state)

            # Should have called answer twice (loading + user list)
            self.assertEqual(self.message.answer.await_count, 2)

            final_call = self.message.answer.await_args
            user_list = final_call[0][0]
            self.assertIn("All Users", user_list)
            self.assertIn("123", user_list)
            self.assertIn("456", user_list)

    async def test_view_all_users_no_users(self):
        """Test view all users when no users exist."""
        with patch.object(self.ahandlers, "is_admin", return_value=True), patch.object(
            self.ahandlers, "get_repository"
        ) as mock_repo:

            mock_client = MagicMock()
            mock_repo.return_value._client = mock_client
            mock_client.get_all_tasks = AsyncMock(return_value={"tasks": []})

            await self.ahandlers.view_all_users(self.message, self.state)

            final_call = self.message.answer.await_args
            self.assertIn("No users found", final_call[0][0])

    async def test_view_all_tasks_access_denied(self):
        """Test view all tasks denies non-admin users."""
        with patch.object(self.ahandlers, "is_admin", return_value=False):
            await self.ahandlers.view_all_tasks(self.message, self.state)
            self.message.answer.assert_awaited_once()
            call_args = self.message.answer.await_args
            self.assertIn("Access denied", call_args[0][0])

    async def test_view_all_tasks_success(self):
        """Test view all tasks displays task list."""
        with patch.object(self.ahandlers, "is_admin", return_value=True), patch.object(
            self.ahandlers, "get_repository"
        ) as mock_repo:

            mock_client = MagicMock()
            mock_repo.return_value._client = mock_client
            mock_client.get_all_tasks = AsyncMock(
                return_value={
                    "tasks": [
                        {
                            "name": "Task1",
                            "chat_id": "123",
                            "is_active": True,
                            "last_updated": "2025-01-01T12:00:00Z",
                        },
                        {
                            "name": "Task2",
                            "chat_id": "456",
                            "is_active": False,
                            "last_updated": "2025-01-02T12:00:00Z",
                        },
                    ]
                }
            )

            await self.ahandlers.view_all_tasks(self.message, self.state)

            # Should have called answer twice (loading + task list)
            self.assertEqual(self.message.answer.await_count, 2)

            final_call = self.message.answer.await_args
            task_list = final_call[0][0]
            self.assertIn("All Monitoring Tasks", task_list)
            self.assertIn("Task1", task_list)
            self.assertIn("Task2", task_list)

    async def test_view_all_tasks_no_tasks(self):
        """Test view all tasks when no tasks exist."""
        with patch.object(self.ahandlers, "is_admin", return_value=True), patch.object(
            self.ahandlers, "get_repository"
        ) as mock_repo:

            mock_client = MagicMock()
            mock_repo.return_value._client = mock_client
            mock_client.get_all_tasks = AsyncMock(return_value={"tasks": []})

            await self.ahandlers.view_all_tasks(self.message, self.state)

            final_call = self.message.answer.await_args
            self.assertIn("No monitoring tasks found", final_call[0][0])

    async def test_view_recent_errors_access_denied(self):
        """Test view recent errors denies non-admin users."""
        with patch.object(self.ahandlers, "is_admin", return_value=False):
            await self.ahandlers.view_recent_errors(self.message, self.state)
            self.message.answer.assert_awaited_once()
            call_args = self.message.answer.await_args
            self.assertIn("Access denied", call_args[0][0])

    async def test_view_recent_errors_success(self):
        """Test view recent errors displays error log."""
        with patch.object(self.ahandlers, "is_admin", return_value=True), patch(
            "builtins.open", create=True
        ) as mock_open:

            # Mock log file content
            mock_file = MagicMock()
            mock_file.__enter__.return_value = mock_file
            mock_file.readlines.return_value = [
                "2025-01-01 12:00:00 - ERROR - Test error 1\n",
                "2025-01-01 12:01:00 - INFO - Normal log\n",
                "2025-01-01 12:02:00 - ERROR - Test error 2\n",
                "2025-01-01 12:03:00 - CRITICAL - Critical error\n",
            ]
            mock_open.return_value = mock_file

            await self.ahandlers.view_recent_errors(self.message, self.state)

            self.message.answer.assert_awaited_once()
            call_args = self.message.answer.await_args
            error_text = call_args[0][0]
            self.assertIn("Recent Errors", error_text)
            self.assertIn("Test error 1", error_text)
            self.assertIn("Test error 2", error_text)
            self.assertIn("Critical error", error_text)
            # Should not include INFO log
            self.assertNotIn("Normal log", error_text)

    async def test_view_recent_errors_no_errors(self):
        """Test view recent errors when no errors exist."""
        with patch.object(self.ahandlers, "is_admin", return_value=True), patch(
            "builtins.open", create=True
        ) as mock_open:

            # Mock log file with no errors
            mock_file = MagicMock()
            mock_file.__enter__.return_value = mock_file
            mock_file.readlines.return_value = [
                "2025-01-01 12:00:00 - INFO - Normal log 1\n",
                "2025-01-01 12:01:00 - INFO - Normal log 2\n",
            ]
            mock_open.return_value = mock_file

            await self.ahandlers.view_recent_errors(self.message, self.state)

            self.message.answer.assert_awaited_once()
            call_args = self.message.answer.await_args
            self.assertIn("No recent errors found", call_args[0][0])

    async def test_view_recent_errors_no_log_file(self):
        """Test view recent errors when log file doesn't exist."""
        with patch.object(self.ahandlers, "is_admin", return_value=True), patch(
            "builtins.open", side_effect=FileNotFoundError
        ):

            await self.ahandlers.view_recent_errors(self.message, self.state)

            self.message.answer.assert_awaited_once()
            call_args = self.message.answer.await_args
            self.assertIn("No log file found", call_args[0][0])

    async def test_back_to_main_menu(self):
        """Test back to main menu returns to main menu."""
        await self.ahandlers.back_to_main_menu(self.message, self.state)

        self.state.clear.assert_awaited_once()
        self.message.answer.assert_awaited_once()
        call_args = self.message.answer.await_args
        self.assertIn("Back to main menu", call_args[0][0])
        self.assertIn("reply_markup", call_args[1])


class TestAdminAccessControl(IsolatedAsyncioTestCase):
    """Test admin access control across all handlers."""

    def setUp(self):
        from bot.handlers import admin as ahandlers

        self.ahandlers = ahandlers
        self.message = MagicMock()
        self.message.chat = MagicMock(id=999999)  # Non-admin user
        self.message.answer = AsyncMock()
        self.state = MagicMock()
        self.state.clear = AsyncMock()

    async def test_all_handlers_deny_non_admin(self):
        """Test that all admin handlers deny non-admin users."""
        handlers = [
            self.ahandlers.admin_panel_menu,
            self.ahandlers.system_status,
            self.ahandlers.view_all_users,
            self.ahandlers.view_all_tasks,
            self.ahandlers.view_recent_errors,
        ]

        with patch.object(self.ahandlers, "is_admin", return_value=False):
            for handler in handlers:
                self.message.answer.reset_mock()
                await handler(self.message, self.state)
                self.message.answer.assert_awaited()
                call_args = self.message.answer.await_args
                # All should show access denied
                self.assertIn("Access denied", call_args[0][0].lower())
