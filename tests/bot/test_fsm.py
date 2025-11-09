from unittest import IsolatedAsyncioTestCase

from aiogram.fsm.state import State

from bot.fsm import StartMonitoringForm, StatusForm, StopMonitoringForm


class TestStartMonitoringForm(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        pass

    async def asyncTearDown(self):
        pass

    async def test_states_exist(self):
        self.assertIsInstance(StartMonitoringForm.url, State)
        self.assertIsInstance(StartMonitoringForm.name, State)


class TestStopMonitoringForm(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        pass

    async def asyncTearDown(self):
        pass

    async def test_states_exist(self):
        self.assertIsInstance(StopMonitoringForm.choosing, State)


class TestStatusForm(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        pass

    async def asyncTearDown(self):
        pass

    async def test_states_exist(self):
        self.assertIsInstance(StatusForm.choosing, State)


from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import types


class TestKeyboards(IsolatedAsyncioTestCase):
    async def test_main_menu_keyboard_structure_non_admin(self):
        from bot.keyboards import get_main_menu_keyboard

        # Test for non-admin user
        keyboard = get_main_menu_keyboard(chat_id=999999)
        self.assertIsInstance(keyboard, types.ReplyKeyboardMarkup)
        # Two rows: [Start, Stop], [Status]
        rows = keyboard.keyboard
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]), 2)
        self.assertEqual(rows[0][0].text, "Start monitoring")
        self.assertEqual(rows[0][1].text, "Stop monitoring")
        self.assertEqual(len(rows[1]), 1)
        self.assertEqual(rows[1][0].text, "Status")
        self.assertTrue(keyboard.resize_keyboard)

    async def test_main_menu_keyboard_structure_admin(self):
        from unittest.mock import patch

        from bot.keyboards import get_main_menu_keyboard
        from core import config

        # Mock the Settings.is_admin method to return True
        with patch.object(config.Settings, "is_admin", return_value=True):
            keyboard = get_main_menu_keyboard(chat_id=123456)
            self.assertIsInstance(keyboard, types.ReplyKeyboardMarkup)
            # Three rows: [Start, Stop], [Status], [Admin Panel]
            rows = keyboard.keyboard
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[2][0].text, "🔧 Admin Panel")

    async def test_get_monitoring_selection_keyboard(self):
        from bot.keyboards import BACK_BUTTON, get_monitoring_selection_keyboard

        kb = get_monitoring_selection_keyboard(["A", "B"])
        self.assertIsInstance(kb, types.ReplyKeyboardMarkup)
        rows = kb.keyboard
        self.assertEqual([btn.text for btn in rows[0]], ["A"])  # one per row
        self.assertEqual([btn.text for btn in rows[1]], ["B"])  # one per row
        self.assertEqual(rows[-1][0].text, BACK_BUTTON.text)


class TestMonitoringHandlers(IsolatedAsyncioTestCase):
    def setUp(self):
        from bot.handlers import monitoring as mhandlers

        self.mhandlers = mhandlers

        # Common mocks
        self.message = MagicMock()
        self.message.chat = MagicMock(id=123)
        self.message.answer = AsyncMock()
        self.state = MagicMock()
        self.state.set_state = AsyncMock()
        self.state.clear = AsyncMock()
        self.state.update_data = AsyncMock()
        self.state.get_data = AsyncMock()

    async def test_cmd_start_monitoring(self):
        await self.mhandlers.cmd_start_monitoring(self.message, self.state)
        self.state.set_state.assert_awaited()
        self.message.answer.assert_awaited()

    async def test_process_url_back(self):
        self.message.text = self.mhandlers.BACK_BUTTON.text
        await self.mhandlers.process_url(self.message, self.state)
        # Check that answer was called with BACK_TO_MENU and some keyboard
        call_args = self.message.answer.await_args
        self.assertEqual(call_args[0][0], self.mhandlers.BACK_TO_MENU)
        self.assertIn("reply_markup", call_args[1])
        self.state.clear.assert_awaited()

    async def test_process_url_invalid(self):
        self.message.text = "http://example.com"
        with patch.object(self.mhandlers, "UrlValidator") as V:
            inst = V.return_value
            inst.is_supported.return_value = False
            await self.mhandlers.process_url(self.message, self.state)
            self.message.answer.assert_awaited_with(self.mhandlers.INVALID_URL)

    async def test_process_url_unreachable(self):
        self.message.text = "https://www.olx.pl/x"
        with patch.object(self.mhandlers, "UrlValidator") as V:
            inst = V.return_value
            inst.is_supported.return_value = True
            inst.normalize.side_effect = lambda u: u
            inst.is_reachable = AsyncMock(return_value=False)
            await self.mhandlers.process_url(self.message, self.state)
            self.message.answer.assert_awaited_with(self.mhandlers.URL_NOT_REACHABLE)

    async def test_process_url_duplicate_and_exception(self):
        self.message.text = "https://www.olx.pl/x"
        with patch.object(self.mhandlers, "UrlValidator") as V, patch.object(
            self.mhandlers, "get_monitoring_service"
        ) as G:
            inst = V.return_value
            inst.is_supported.return_value = True
            inst.normalize.side_effect = lambda u: u
            inst.is_reachable = AsyncMock(return_value=True)
            svc = G.return_value
            svc._repo.has_url = AsyncMock(return_value=True)
            await self.mhandlers.process_url(self.message, self.state)
            self.message.answer.assert_awaited_with(self.mhandlers.DUPLICATE_URL)

            # Exception path
            self.message.answer.reset_mock()
            svc._repo.has_url = AsyncMock(side_effect=Exception("boom"))
            await self.mhandlers.process_url(self.message, self.state)
            self.message.answer.assert_awaited_with(self.mhandlers.ERROR_CREATING)

    async def test_process_url_success_to_name(self):
        self.message.text = "https://www.olx.pl/x"
        with patch.object(self.mhandlers, "UrlValidator") as V, patch.object(
            self.mhandlers, "get_monitoring_service"
        ) as G:
            inst = V.return_value
            inst.is_supported.return_value = True
            inst.normalize.side_effect = lambda u: u
            inst.is_reachable = AsyncMock(return_value=True)
            svc = G.return_value
            svc._repo.has_url = AsyncMock(return_value=False)
            await self.mhandlers.process_url(self.message, self.state)
            self.state.set_state.assert_awaited_with(
                self.mhandlers.StartMonitoringForm.name
            )
            self.message.answer.assert_awaited()

    async def test_process_name_back_and_invalid(self):
        # back
        self.message.text = self.mhandlers.BACK_BUTTON.text
        await self.mhandlers.process_name(self.message, self.state)
        # Check that answer was called with BACK_TO_MENU and some keyboard
        call_args = self.message.answer.await_args
        self.assertEqual(call_args[0][0], self.mhandlers.BACK_TO_MENU)
        self.assertIn("reply_markup", call_args[1])
        self.state.clear.assert_awaited()

        # invalid length
        self.message.answer.reset_mock()
        self.state.clear.reset_mock()
        self.message.text = ""
        await self.mhandlers.process_name(self.message, self.state)
        self.message.answer.assert_awaited_with(self.mhandlers.INVALID_NAME)

    async def test_process_name_success_and_errors(self):
        self.message.text = "goodname"
        self.state.get_data.return_value = {"url": "https://www.olx.pl/x"}
        with patch.object(self.mhandlers, "get_monitoring_service") as G:
            svc = G.return_value
            svc.add_monitoring = AsyncMock()
            await self.mhandlers.process_name(self.message, self.state)
            # success path answers created and clears
            self.assertTrue(self.message.answer.await_count >= 1)
            self.state.clear.assert_awaited()

            # duplicate name ValueError
            self.message.answer.reset_mock()
            self.state.clear.reset_mock()
            svc.add_monitoring = AsyncMock(side_effect=ValueError("Duplicate name"))
            await self.mhandlers.process_name(self.message, self.state)
            self.message.answer.assert_awaited_with(self.mhandlers.DUPLICATE_NAME)

            # generic error
            self.message.answer.reset_mock()
            svc.add_monitoring = AsyncMock(side_effect=Exception("x"))
            await self.mhandlers.process_name(self.message, self.state)
            self.message.answer.assert_awaited_with(self.mhandlers.ERROR_CREATING)

    async def test_stop_monitoring_command_paths(self):
        with patch.object(self.mhandlers, "get_monitoring_service") as G, patch.object(
            self.mhandlers, "get_monitoring_selection_keyboard"
        ) as GK:
            svc = G.return_value
            # no tasks
            svc.list_monitorings = AsyncMock(return_value=[])
            await self.mhandlers.stop_monitoring_command(self.message, self.state)
            self.assertTrue(self.message.answer.await_count >= 1)

            # some tasks
            self.message.answer.reset_mock()
            task = MagicMock(name="n1")
            svc.list_monitorings = AsyncMock(return_value=[task])
            await self.mhandlers.stop_monitoring_command(self.message, self.state)
            self.state.set_state.assert_awaited_with(
                self.mhandlers.StopMonitoringForm.choosing
            )

            # exception
            self.message.answer.reset_mock()
            svc.list_monitorings = AsyncMock(side_effect=Exception("e"))
            await self.mhandlers.stop_monitoring_command(self.message, self.state)
            self.message.answer.assert_awaited_with(self.mhandlers.ERROR_STOP)

    async def test_process_stop_choice_paths(self):
        with patch.object(self.mhandlers, "get_monitoring_service") as G:
            svc = G.return_value
            # back
            self.message.text = self.mhandlers.BACK_BUTTON.text
            await self.mhandlers.process_stop_choice(self.message, self.state)
            self.state.clear.assert_awaited()

            # reserved name
            self.message.text = "/cmd"
            await self.mhandlers.process_stop_choice(self.message, self.state)
            self.message.answer.assert_awaited_with(self.mhandlers.RESERVED_NAME)

            # success
            self.message.answer.reset_mock()
            self.message.text = "nm"
            svc.remove_monitoring = AsyncMock()
            await self.mhandlers.process_stop_choice(self.message, self.state)
            self.assertTrue(self.message.answer.await_count >= 1)

            # not found
            self.message.answer.reset_mock()
            svc.remove_monitoring = AsyncMock(side_effect=ValueError("not found"))
            await self.mhandlers.process_stop_choice(self.message, self.state)
            self.message.answer.assert_awaited_with(self.mhandlers.UNKNOWN_MONITORING)

            # other ValueError
            self.message.answer.reset_mock()
            svc.remove_monitoring = AsyncMock(side_effect=ValueError("bad"))
            await self.mhandlers.process_stop_choice(self.message, self.state)
            self.message.answer.assert_awaited_with(self.mhandlers.ERROR_STOP)

            # generic error
            self.message.answer.reset_mock()
            svc.remove_monitoring = AsyncMock(side_effect=Exception("e"))
            await self.mhandlers.process_stop_choice(self.message, self.state)
            self.message.answer.assert_awaited_with(self.mhandlers.ERROR_STOP)

    async def test_status_command_and_choice(self):
        with patch.object(self.mhandlers, "get_monitoring_service") as G, patch.object(
            self.mhandlers, "_send_status", new=AsyncMock()
        ) as S, patch.object(self.mhandlers, "get_monitoring_selection_keyboard") as GK:
            svc = G.return_value
            # no tasks
            svc.list_monitorings = AsyncMock(return_value=[])
            await self.mhandlers.status_command(self.message, self.state)
            self.message.answer.assert_awaited_with(
                self.mhandlers.NO_MONITORINGS, parse_mode="Markdown"
            )

            # one task
            self.message.answer.reset_mock()
            S.reset_mock()
            task = MagicMock(name="n1")
            svc.list_monitorings = AsyncMock(return_value=[task])
            await self.mhandlers.status_command(self.message, self.state)
            S.assert_awaited_with(self.message, task)

            # multiple tasks
            self.message.answer.reset_mock()
            self.state.set_state.reset_mock()
            task2 = MagicMock(name="n2")
            svc.list_monitorings = AsyncMock(return_value=[task, task2])
            await self.mhandlers.status_command(self.message, self.state)
            self.state.set_state.assert_awaited_with(self.mhandlers.StatusForm.choosing)

            # exception
            self.message.answer.reset_mock()
            svc.list_monitorings = AsyncMock(side_effect=Exception("e"))
            await self.mhandlers.status_command(self.message, self.state)
            self.message.answer.assert_awaited_with(
                "Error retrieving monitoring status."
            )

        # process_status_choice paths
        with patch.object(self.mhandlers, "get_monitoring_service") as G, patch.object(
            self.mhandlers, "_send_status", new=AsyncMock()
        ) as S:
            svc = G.return_value
            # back
            self.message.text = self.mhandlers.BACK_BUTTON.text
            await self.mhandlers.process_status_choice(self.message, self.state)
            self.state.clear.assert_awaited()

            # found
            self.message.text = "n2"
            t1 = MagicMock(name="n1")
            t1.name = "n1"
            t2 = MagicMock(name="n2")
            t2.name = "n2"
            svc.list_monitorings = AsyncMock(return_value=[t1, t2])
            await self.mhandlers.process_status_choice(self.message, self.state)
            S.assert_awaited_with(self.message, t2)
            # Should also answer MAIN_MENU
            self.assertTrue(self.message.answer.await_count >= 1)

            # not found
            self.message.answer.reset_mock()
            self.message.text = "unknown"
            await self.mhandlers.process_status_choice(self.message, self.state)
            self.message.answer.assert_awaited_with(self.mhandlers.UNKNOWN_MONITORING)

            # exception
            self.message.answer.reset_mock()
            svc.list_monitorings = AsyncMock(side_effect=Exception("e"))
            await self.mhandlers.process_status_choice(self.message, self.state)
            self.message.answer.assert_awaited_with(
                "Error retrieving monitoring status."
            )

    async def test_send_status_formatting(self):
        # None values => "Never" in both fields
        task = MagicMock(name="t")
        task.name = "t"
        task.url = "https://u"
        task.last_updated = None
        task.last_got_item = None
        await self.mhandlers._send_status(self.message, task)
        args, kwargs = self.message.answer.await_args
        self.assertIn("Never", args[0])

        # ISO string
        self.message.answer.reset_mock()
        task.last_updated = "2025-01-01T12:00:00Z"
        task.last_got_item = "2025-01-01T12:00:00Z"
        await self.mhandlers._send_status(self.message, task)
        args, kwargs = self.message.answer.await_args
        self.assertIn("2025-01-01 12:00:00", args[0])

        # datetime object
        from datetime import datetime

        self.message.answer.reset_mock()
        dt = datetime(2025, 1, 1, 12, 0, 0)
        task.last_updated = dt
        task.last_got_item = dt
        await self.mhandlers._send_status(self.message, task)
        args, kwargs = self.message.answer.await_args
        self.assertIn("2025-01-01 12:00:00", args[0])
