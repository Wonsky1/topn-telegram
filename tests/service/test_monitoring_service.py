from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

from services.monitoring import MonitoringService, MonitoringSpec


class TestMonitoringService(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.repo = AsyncMock()
        self.validator = MagicMock()
        self.validator.is_supported.return_value = True
        self.validator.normalize.side_effect = lambda u: u
        self.validator.is_reachable = AsyncMock(return_value=True)
        self.svc = MonitoringService(self.repo, self.validator)

    async def asyncTearDown(self):
        pass

    async def test_add_monitoring_happy_path(self):
        self.repo.has_url.return_value = False
        self.repo.task_exists.return_value = False
        spec = MonitoringSpec(chat_id="1", name="ok", url="https://www.olx.pl/")
        await self.svc.add_monitoring(spec)
        self.repo.create_task.assert_awaited_with(
            chat_id="1",
            name="ok",
            url="https://www.olx.pl/",
            city_id=None,
            allowed_district_ids=None,
        )

    async def test_add_monitoring_with_city_and_districts(self):
        self.repo.has_url.return_value = False
        self.repo.task_exists.return_value = False
        spec = MonitoringSpec(
            chat_id="1",
            name="ok",
            url="https://www.olx.pl/",
            city_id=5,
            allowed_district_ids=[1, 2, 3],
        )
        await self.svc.add_monitoring(spec)
        self.repo.create_task.assert_awaited_with(
            chat_id="1",
            name="ok",
            url="https://www.olx.pl/",
            city_id=5,
            allowed_district_ids=[1, 2, 3],
        )

    async def test_add_monitoring_bad_name(self):
        for bad in ("", "/cmd", "x" * 65):
            spec = MonitoringSpec(chat_id="1", name=bad, url="https://www.olx.pl/")
            with self.assertRaises(ValueError):
                await self.svc.add_monitoring(spec)

    async def test_add_monitoring_unsupported_url(self):
        self.validator.is_supported.return_value = False
        spec = MonitoringSpec(chat_id="1", name="ok", url="bad")
        with self.assertRaises(ValueError):
            await self.svc.add_monitoring(spec)

    async def test_add_monitoring_unreachable(self):
        self.validator.is_supported.return_value = True
        self.validator.is_reachable.return_value = False
        spec = MonitoringSpec(chat_id="1", name="ok", url="https://www.olx.pl/")
        with self.assertRaises(ValueError):
            await self.svc.add_monitoring(spec)

    async def test_add_monitoring_duplicates(self):
        # Duplicate URL
        self.repo.has_url.return_value = True
        spec = MonitoringSpec(chat_id="1", name="ok", url="https://www.olx.pl/")
        with self.assertRaises(ValueError):
            await self.svc.add_monitoring(spec)
        # Duplicate name
        self.repo.has_url.return_value = False
        self.repo.task_exists.return_value = True
        with self.assertRaises(ValueError):
            await self.svc.add_monitoring(spec)

    async def test_remove_monitoring_checks_existence(self):
        self.repo.task_exists.return_value = False
        with self.assertRaises(ValueError):
            await self.svc.remove_monitoring("1", "n")
        self.repo.task_exists.return_value = True
        await self.svc.remove_monitoring("1", "n")
        self.repo.delete_task.assert_awaited_with("1", "n")

    async def test_passthroughs(self):
        await self.svc.list_monitorings("1")
        self.repo.list_tasks.assert_awaited_with("1")
        await self.svc.pending_tasks()
        self.repo.pending_tasks.assert_awaited()
        await self.svc.items_to_send(MagicMock())
        self.repo.items_to_send.assert_awaited()
        await self.svc.update_last_got_item("1")
        self.repo.update_last_got_item.assert_awaited_with("1")
        await self.svc.update_last_updated(MagicMock())
        self.repo.update_last_updated.assert_awaited()
