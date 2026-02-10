"""Inline keyboards for interactive selections.

This module provides inline keyboards with callback data for:
- District selection with pagination
- Toggle selections
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Constants
DISTRICTS_PER_PAGE = 6

# Callback data prefixes
CB_DISTRICT_TOGGLE = "district_toggle"
CB_DISTRICT_PAGE = "district_page"
CB_DISTRICT_SAVE = "district_save"
CB_DISTRICT_SKIP = "district_skip"
CB_DISTRICT_BACK = "district_back"


@dataclass
class DistrictItem:
    """Represents a district for keyboard display."""

    id: int
    name: str
    is_selected: bool = False


def _create_district_button(district: DistrictItem) -> InlineKeyboardButton:
    """Create a toggle button for a district.

    Args:
        district: District item with selection state

    Returns:
        InlineKeyboardButton with checkbox emoji and callback data
    """
    checkbox = "✅" if district.is_selected else "⬜"
    return InlineKeyboardButton(
        text=f"{checkbox} {district.name}",
        callback_data=f"{CB_DISTRICT_TOGGLE}:{district.id}",
    )


def build_districts_keyboard(
    districts: List[DistrictItem],
    selected_ids: set[int],
    current_page: int = 0,
) -> InlineKeyboardMarkup:
    """Build inline keyboard for district selection with pagination.

    Args:
        districts: List of all available districts
        selected_ids: Set of currently selected district IDs
        current_page: Current page number (0-indexed)

    Returns:
        InlineKeyboardMarkup with district toggles and navigation
    """
    # Update selection state
    for district in districts:
        district.is_selected = district.id in selected_ids

    # Calculate pagination
    total_districts = len(districts)
    total_pages = max(
        1, (total_districts + DISTRICTS_PER_PAGE - 1) // DISTRICTS_PER_PAGE
    )
    current_page = min(max(0, current_page), total_pages - 1)

    start_idx = current_page * DISTRICTS_PER_PAGE
    end_idx = min(start_idx + DISTRICTS_PER_PAGE, total_districts)
    page_districts = districts[start_idx:end_idx]

    # Build keyboard rows
    keyboard: List[List[InlineKeyboardButton]] = []

    # District buttons (2 per row for better mobile UX)
    for i in range(0, len(page_districts), 2):
        row = [_create_district_button(page_districts[i])]
        if i + 1 < len(page_districts):
            row.append(_create_district_button(page_districts[i + 1]))
        keyboard.append(row)

    # Navigation row (pagination)
    if total_pages > 1:
        nav_row: List[InlineKeyboardButton] = []

        # Previous button
        if current_page > 0:
            nav_row.append(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"{CB_DISTRICT_PAGE}:{current_page - 1}",
                )
            )
        else:
            nav_row.append(InlineKeyboardButton(text=" ", callback_data="noop"))

        # Page indicator
        nav_row.append(
            InlineKeyboardButton(
                text=f"{current_page + 1}/{total_pages}",
                callback_data="noop",
            )
        )

        # Next button
        if current_page < total_pages - 1:
            nav_row.append(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"{CB_DISTRICT_PAGE}:{current_page + 1}",
                )
            )
        else:
            nav_row.append(InlineKeyboardButton(text=" ", callback_data="noop"))

        keyboard.append(nav_row)

    # Selection info
    selected_count = len(selected_ids)
    if selected_count > 0:
        info_text = f"Selected: {selected_count}"
    else:
        info_text = "All districts (none selected)"

    keyboard.append([InlineKeyboardButton(text=info_text, callback_data="noop")])

    # Action buttons
    keyboard.append(
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data=CB_DISTRICT_BACK),
            InlineKeyboardButton(
                text="⏭ Skip (all)",
                callback_data=CB_DISTRICT_SKIP,
            ),
            InlineKeyboardButton(text="💾 Save", callback_data=CB_DISTRICT_SAVE),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_districts_from_api_response(
    districts_data: List[Dict],
    selected_ids: set[int] | None = None,
) -> List[DistrictItem]:
    """Convert API response to DistrictItem list.

    Args:
        districts_data: List of district dicts from API
        selected_ids: Optional set of pre-selected IDs

    Returns:
        List of DistrictItem objects
    """
    selected_ids = selected_ids or set()
    return [
        DistrictItem(
            id=d["id"],
            name=d["name_raw"],
            is_selected=d["id"] in selected_ids,
        )
        for d in districts_data
        # Skip "Unknown" district
        if d.get("name_normalized", "").lower() != "unknown"
    ]
