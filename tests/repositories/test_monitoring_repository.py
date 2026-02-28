import asyncio
import os
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from repositories.monitoring import MonitoringRepository, MonitoringTask


class TestMonitoringRepository(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        os.environ.setdefault("TOPN_DB_BASE_URL", "http://localhost:8000")
        self.client = AsyncMock()
        self.repo = MonitoringRepository(client=self.client)

    async def asyncTearDown(self):
        pass

    async def test_task_exists_true_false(self):
        self.client.get_tasks_by_chat_id.return_value = {
            "tasks": [{"name": "foo"}, {"name": "bar"}]
        }
        self.assertTrue(await self.repo.task_exists("1", "foo"))
        self.assertFalse(await self.repo.task_exists("1", "baz"))

    async def test_has_url_uses_static_helper(self):
        with patch.object(
            MonitoringTask, "has_url_for_chat", new_callable=AsyncMock
        ) as h:
            h.return_value = True
            self.assertTrue(await self.repo.has_url("1", "u"))
            h.assert_awaited_with(self.client, "1", "u")

    async def test_create_task_wraps_response(self):
        self.client.create_task.return_value = {"task": {"id": 5, "name": "x"}}
        task = await self.repo.create_task("1", "x", "u")
        self.assertIsInstance(task, MonitoringTask)
        self.assertEqual(task.id, 5)

    async def test_delete_task_calls_client(self):
        await self.repo.delete_task("1", "n")
        self.client.delete_tasks_by_chat_id.assert_awaited_with("1", "n")

    async def test_list_tasks_builds_models(self):
        self.client.get_tasks_by_chat_id.return_value = {
            "tasks": [
                {"id": 1, "name": "a"},
                {"id": 2, "name": "b"},
            ]
        }
        tasks = await self.repo.list_tasks("1")
        self.assertEqual([t.id for t in tasks], [1, 2])

    async def test_pending_tasks(self):
        self.client.get_pending_tasks.return_value = {"tasks": [{"id": 10}, {"id": 11}]}
        tasks = await self.repo.pending_tasks()
        self.assertEqual([t.id for t in tasks], [10, 11])

    async def test_items_to_send(self):
        self.client.get_items_to_send_for_task.return_value = {"items": [1, 2, 3]}
        items = await self.repo.items_to_send(MagicMock(id=7))
        self.assertEqual(items, [1, 2, 3])

    async def test_update_last_got_item_updates_specific_task(self):
        await self.repo.update_last_got_item(42)
        self.client.update_last_got_item_timestamp.assert_awaited_once_with(42)

    async def test_update_last_updated_sets_timestamp(self):
        with patch("repositories.monitoring.now_warsaw") as n:
            n.return_value.isoformat.return_value = "2020-01-01T00:00:00"
            await self.repo.update_last_updated(MagicMock(id=9))
            self.client.update_task.assert_awaited_with(
                9, {"last_updated": "2020-01-01T00:00:00"}
            )

    async def test_remove_old_items_data_infinitely_one_iteration(self):
        # Break the loop after first sleep
        self.client.delete_old_items.return_value = {"ok": True}

        async def fake_sleep(_):
            raise asyncio.CancelledError

        with patch("repositories.monitoring.asyncio.sleep", new=fake_sleep):
            with self.assertRaises(asyncio.CancelledError):
                await self.repo.remove_old_items_data_infinitely(3)
        self.client.delete_old_items.assert_awaited_with(3)

    async def test_has_url_for_chat_exception_returns_false(self):
        # Static helper should return False on exception
        self.client.get_tasks_by_chat_id.side_effect = Exception("boom")
        res = await MonitoringTask.has_url_for_chat(self.client, "1", "u")
        self.assertFalse(res)

    async def test_task_exists_exception_returns_false(self):
        self.client.get_tasks_by_chat_id.side_effect = Exception("err")
        self.assertFalse(await self.repo.task_exists("1", "x"))

    async def test_create_task_exception_propagates(self):
        self.client.create_task.side_effect = Exception("create-error")
        with self.assertRaises(Exception):
            await self.repo.create_task("1", "n", "u")

    async def test_delete_task_exception_propagates(self):
        self.client.delete_tasks_by_chat_id.side_effect = Exception("del-error")
        with self.assertRaises(Exception):
            await self.repo.delete_task("1", "n")

    async def test_list_tasks_exception_returns_empty(self):
        self.client.get_tasks_by_chat_id.side_effect = Exception("list-error")
        tasks = await self.repo.list_tasks("1")
        self.assertEqual(tasks, [])

    async def test_pending_tasks_exception_returns_empty(self):
        self.client.get_pending_tasks.side_effect = Exception("p-error")
        tasks = await self.repo.pending_tasks()
        self.assertEqual(tasks, [])

    async def test_items_to_send_exception_returns_empty(self):
        self.client.get_items_to_send_for_task.side_effect = Exception("it-error")
        items = await self.repo.items_to_send(MagicMock(id=123))
        self.assertEqual(items, [])

    async def test_update_last_got_item_handles_exception(self):
        self.client.update_last_got_item_timestamp.side_effect = Exception("u-error")
        await self.repo.update_last_got_item(42)

    async def test_update_last_updated_handles_exception(self):
        self.client.update_task.side_effect = Exception("upd-error")
        await self.repo.update_last_updated(MagicMock(id=9))

    async def test_remove_old_items_data_infinitely_handles_exception_then_sleep(self):
        # delete_old_items throws, but loop continues to sleep
        self.client.delete_old_items.side_effect = Exception("clean-error")

        async def fake_sleep(_):
            raise asyncio.CancelledError

        with patch("repositories.monitoring.asyncio.sleep", new=fake_sleep):
            with self.assertRaises(asyncio.CancelledError):
                await self.repo.remove_old_items_data_infinitely(5)
        self.client.delete_old_items.assert_awaited_with(5)
