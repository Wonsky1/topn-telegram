"""Tests for district selection callback handlers."""

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

from aiogram.types import CallbackQuery, Message, User

from bot.handlers.districts import (
    handle_district_back,
    handle_district_page,
    handle_district_save,
    handle_district_skip,
    handle_district_toggle,
    handle_noop,
)
from bot.keyboards_inline import CB_DISTRICT_TOGGLE


def create_mock_callback(data: str, message: MagicMock = None) -> MagicMock:
    """Create a mock callback query."""
    callback = MagicMock(spec=CallbackQuery)
    callback.data = data
    callback.message = message or MagicMock(spec=Message)
    callback.message.delete = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.message.edit_reply_markup = AsyncMock()
    callback.from_user = MagicMock(spec=User)
    callback.from_user.id = 12345
    callback.answer = AsyncMock()
    return callback


class TestHandleDistrictToggle(IsolatedAsyncioTestCase):
    """Tests for handle_district_toggle handler."""

    async def test_toggle_selects_district(self):
        callback = create_mock_callback(f"{CB_DISTRICT_TOGGLE}:5")
        state = AsyncMock()
        state.get_data.return_value = {
            "selected_district_ids": [],
            "districts_data": [
                {"id": 5, "name_raw": "Mokotów", "name_normalized": "mokotow"}
            ],
            "districts_page": 0,
        }

        await handle_district_toggle(callback, state)

        # Check that district was added to selection
        state.update_data.assert_called()
        call_args = state.update_data.call_args
        assert 5 in call_args.kwargs["selected_district_ids"]

    async def test_toggle_deselects_district(self):
        callback = create_mock_callback(f"{CB_DISTRICT_TOGGLE}:5")
        state = AsyncMock()
        state.get_data.return_value = {
            "selected_district_ids": [5],
            "districts_data": [
                {"id": 5, "name_raw": "Mokotów", "name_normalized": "mokotow"}
            ],
            "districts_page": 0,
        }

        await handle_district_toggle(callback, state)

        # Check that district was removed from selection
        state.update_data.assert_called()
        call_args = state.update_data.call_args
        assert 5 not in call_args.kwargs["selected_district_ids"]

    async def test_toggle_invalid_data(self):
        callback = create_mock_callback("district_toggle:invalid")
        state = AsyncMock()

        await handle_district_toggle(callback, state)

        callback.answer.assert_called_with("Invalid district")


class TestHandleDistrictPage(IsolatedAsyncioTestCase):
    """Tests for handle_district_page handler."""

    async def test_page_navigation(self):
        callback = create_mock_callback("district_page:2")
        state = AsyncMock()
        state.get_data.return_value = {
            "selected_district_ids": [],
            "districts_data": [
                {
                    "id": i,
                    "name_raw": f"District {i}",
                    "name_normalized": f"district{i}",
                }
                for i in range(15)
            ],
        }

        await handle_district_page(callback, state)

        state.update_data.assert_called_with(districts_page=2)
        callback.message.edit_reply_markup.assert_called()


class TestHandleDistrictSave(IsolatedAsyncioTestCase):
    """Tests for handle_district_save handler."""

    async def test_save_proceeds_to_name_state(self):
        callback = create_mock_callback("district_save")
        state = AsyncMock()
        state.get_data.return_value = {"selected_district_ids": [1, 2, 3]}

        await handle_district_save(callback, state)

        callback.message.delete.assert_called()
        state.set_state.assert_called()
        callback.message.answer.assert_called()


class TestHandleDistrictSkip(IsolatedAsyncioTestCase):
    """Tests for handle_district_skip handler."""

    async def test_skip_clears_selection(self):
        callback = create_mock_callback("district_skip")
        state = AsyncMock()

        await handle_district_skip(callback, state)

        state.update_data.assert_called_with(selected_district_ids=[])
        callback.message.delete.assert_called()


class TestHandleDistrictBack(IsolatedAsyncioTestCase):
    """Tests for handle_district_back handler."""

    async def test_back_clears_state(self):
        callback = create_mock_callback("district_back")
        state = AsyncMock()

        await handle_district_back(callback, state)

        state.update_data.assert_called()
        callback.message.delete.assert_called()
        state.set_state.assert_called()


class TestHandleNoop(IsolatedAsyncioTestCase):
    """Tests for handle_noop handler."""

    async def test_noop_just_answers(self):
        callback = create_mock_callback("noop")

        await handle_noop(callback)

        callback.answer.assert_called()
