"""Callback handlers for district selection inline keyboard.

This module handles all callback queries related to district selection
during monitoring creation flow.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from bot.fsm import StartMonitoringForm
from bot.keyboards_inline import (
    CB_DISTRICT_BACK,
    CB_DISTRICT_PAGE,
    CB_DISTRICT_SAVE,
    CB_DISTRICT_SKIP,
    CB_DISTRICT_TOGGLE,
    DistrictItem,
    build_districts_keyboard,
)
from bot.responses import DISTRICTS_SKIP, SEND_NAME

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Create router for district callbacks
router = Router(name="districts")


@router.callback_query(lambda c: c.data and c.data.startswith(CB_DISTRICT_TOGGLE))
async def handle_district_toggle(callback: types.CallbackQuery, state: FSMContext):
    """Handle district toggle button click."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    # Extract district ID from callback data
    try:
        district_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Invalid district")
        return

    # Get current state data
    data = await state.get_data()
    selected_ids: set[int] = set(data.get("selected_district_ids", []))
    districts_data: list[dict] = data.get("districts_data", [])
    current_page: int = data.get("districts_page", 0)

    # Toggle selection
    if district_id in selected_ids:
        selected_ids.discard(district_id)
    else:
        selected_ids.add(district_id)

    # Update state
    await state.update_data(selected_district_ids=list(selected_ids))

    # Rebuild keyboard
    districts = [
        DistrictItem(
            id=d["id"],
            name=d["name_raw"],
            is_selected=d["id"] in selected_ids,
        )
        for d in districts_data
        if d.get("name_normalized", "").lower() != "unknown"
    ]

    keyboard = build_districts_keyboard(districts, selected_ids, current_page)

    # Update message
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith(CB_DISTRICT_PAGE))
async def handle_district_page(callback: types.CallbackQuery, state: FSMContext):
    """Handle pagination button click."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    # Extract page number from callback data
    try:
        page = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("Invalid page")
        return

    # Get current state data
    data = await state.get_data()
    selected_ids: set[int] = set(data.get("selected_district_ids", []))
    districts_data: list[dict] = data.get("districts_data", [])

    # Update page in state
    await state.update_data(districts_page=page)

    # Rebuild keyboard
    districts = [
        DistrictItem(
            id=d["id"],
            name=d["name_raw"],
            is_selected=d["id"] in selected_ids,
        )
        for d in districts_data
        if d.get("name_normalized", "").lower() != "unknown"
    ]

    keyboard = build_districts_keyboard(districts, selected_ids, page)

    # Update message
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == CB_DISTRICT_SAVE)
async def handle_district_save(callback: types.CallbackQuery, state: FSMContext):
    """Handle save button click — proceed to name input."""
    if not callback.message:
        await callback.answer()
        return

    # Get selected districts
    data = await state.get_data()
    selected_ids: list[int] = data.get("selected_district_ids", [])

    logger.info(
        f"District selection saved for chat_id {callback.from_user.id}: "
        f"{len(selected_ids)} districts selected"
    )

    # Delete the inline keyboard message
    await callback.message.delete()

    # Move to name state
    await state.set_state(StartMonitoringForm.name)

    # Send name prompt
    await callback.message.answer(SEND_NAME)
    await callback.answer()


@router.callback_query(lambda c: c.data == CB_DISTRICT_SKIP)
async def handle_district_skip(callback: types.CallbackQuery, state: FSMContext):
    """Handle skip button click — proceed without district filter."""
    if not callback.message:
        await callback.answer()
        return

    logger.info(f"District selection skipped for chat_id {callback.from_user.id}")

    # Clear selected districts
    await state.update_data(selected_district_ids=[])

    # Delete the inline keyboard message
    await callback.message.delete()

    # Move to name state
    await state.set_state(StartMonitoringForm.name)

    # Send messages
    await callback.message.answer(DISTRICTS_SKIP)
    await callback.message.answer(SEND_NAME)
    await callback.answer()


@router.callback_query(lambda c: c.data == CB_DISTRICT_BACK)
async def handle_district_back(callback: types.CallbackQuery, state: FSMContext):
    """Handle back button click — return to URL input."""
    if not callback.message:
        await callback.answer()
        return

    logger.info(
        f"District selection cancelled (back) for chat_id {callback.from_user.id}"
    )

    # Clear district-related state
    await state.update_data(
        selected_district_ids=[],
        districts_data=[],
        districts_page=0,
        city_id=None,
        city_name=None,
    )

    # Delete the inline keyboard message
    await callback.message.delete()

    # Move back to URL state
    await state.set_state(StartMonitoringForm.url)

    # Send URL prompt
    from bot.responses import SEND_URL

    await callback.message.answer(SEND_URL)
    await callback.answer()


@router.callback_query(lambda c: c.data == "noop")
async def handle_noop(callback: types.CallbackQuery):
    """Handle noop callback (page indicator, info text)."""
    await callback.answer()
