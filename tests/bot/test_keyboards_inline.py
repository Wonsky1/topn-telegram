"""Tests for inline keyboard builders."""

from bot.keyboards_inline import (
    CB_DISTRICT_BACK,
    CB_DISTRICT_PAGE,
    CB_DISTRICT_SAVE,
    CB_DISTRICT_SKIP,
    CB_DISTRICT_TOGGLE,
    DistrictItem,
    build_districts_from_api_response,
    build_districts_keyboard,
)


class TestDistrictItem:
    """Tests for DistrictItem dataclass."""

    def test_create_district_item(self):
        item = DistrictItem(id=1, name="Mokotów")
        assert item.id == 1
        assert item.name == "Mokotów"
        assert item.is_selected is False

    def test_create_selected_district_item(self):
        item = DistrictItem(id=1, name="Mokotów", is_selected=True)
        assert item.is_selected is True


class TestBuildDistrictsKeyboard:
    """Tests for build_districts_keyboard function."""

    def test_empty_districts(self):
        keyboard = build_districts_keyboard([], set(), 0)
        # Should have info row and action buttons
        assert len(keyboard.inline_keyboard) >= 2

    def test_single_district(self):
        districts = [DistrictItem(id=1, name="Mokotów")]
        keyboard = build_districts_keyboard(districts, set(), 0)

        # First row should have the district button
        first_row = keyboard.inline_keyboard[0]
        assert len(first_row) == 1
        assert "Mokotów" in first_row[0].text
        assert first_row[0].callback_data == f"{CB_DISTRICT_TOGGLE}:1"

    def test_selected_district_shows_checkmark(self):
        districts = [DistrictItem(id=1, name="Mokotów")]
        keyboard = build_districts_keyboard(districts, {1}, 0)

        first_row = keyboard.inline_keyboard[0]
        assert "✅" in first_row[0].text

    def test_unselected_district_shows_empty_box(self):
        districts = [DistrictItem(id=1, name="Mokotów")]
        keyboard = build_districts_keyboard(districts, set(), 0)

        first_row = keyboard.inline_keyboard[0]
        assert "⬜" in first_row[0].text

    def test_two_districts_per_row(self):
        districts = [
            DistrictItem(id=1, name="Mokotów"),
            DistrictItem(id=2, name="Ursynów"),
        ]
        keyboard = build_districts_keyboard(districts, set(), 0)

        first_row = keyboard.inline_keyboard[0]
        assert len(first_row) == 2

    def test_pagination_not_shown_for_few_districts(self):
        districts = [DistrictItem(id=i, name=f"District {i}") for i in range(3)]
        keyboard = build_districts_keyboard(districts, set(), 0)

        # Check that no pagination row exists (no page indicator)
        has_pagination = any(
            any(
                btn.callback_data and btn.callback_data.startswith(CB_DISTRICT_PAGE)
                for btn in row
            )
            for row in keyboard.inline_keyboard
        )
        assert has_pagination is False

    def test_pagination_shown_for_many_districts(self):
        districts = [DistrictItem(id=i, name=f"District {i}") for i in range(10)]
        keyboard = build_districts_keyboard(districts, set(), 0)

        # Check that pagination exists
        has_next = any(
            any(btn.callback_data == f"{CB_DISTRICT_PAGE}:1" for btn in row)
            for row in keyboard.inline_keyboard
        )
        assert has_next is True

    def test_action_buttons_present(self):
        districts = [DistrictItem(id=1, name="Mokotów")]
        keyboard = build_districts_keyboard(districts, set(), 0)

        # Get last row (action buttons)
        last_row = keyboard.inline_keyboard[-1]
        callback_data = [btn.callback_data for btn in last_row]

        assert CB_DISTRICT_BACK in callback_data
        assert CB_DISTRICT_SKIP in callback_data
        assert CB_DISTRICT_SAVE in callback_data

    def test_page_navigation(self):
        districts = [DistrictItem(id=i, name=f"District {i}") for i in range(15)]

        # Page 0 - should have next button
        kb_page0 = build_districts_keyboard(districts, set(), 0)
        has_next = any(
            any(btn.callback_data == f"{CB_DISTRICT_PAGE}:1" for btn in row)
            for row in kb_page0.inline_keyboard
        )
        assert has_next is True

        # Page 1 - should have prev button
        kb_page1 = build_districts_keyboard(districts, set(), 1)
        has_prev = any(
            any(btn.callback_data == f"{CB_DISTRICT_PAGE}:0" for btn in row)
            for row in kb_page1.inline_keyboard
        )
        assert has_prev is True

    def test_selection_count_display(self):
        districts = [DistrictItem(id=i, name=f"District {i}") for i in range(3)]
        keyboard = build_districts_keyboard(districts, {0, 1}, 0)

        # Find the info row
        info_text = None
        for row in keyboard.inline_keyboard:
            for btn in row:
                if "Selected:" in btn.text:
                    info_text = btn.text
                    break

        assert info_text is not None
        assert "2" in info_text


class TestBuildDistrictsFromApiResponse:
    """Tests for build_districts_from_api_response function."""

    def test_basic_conversion(self):
        api_data = [
            {"id": 1, "name_raw": "Mokotów", "name_normalized": "mokotow"},
            {"id": 2, "name_raw": "Ursynów", "name_normalized": "ursynow"},
        ]
        result = build_districts_from_api_response(api_data)

        assert len(result) == 2
        assert result[0].id == 1
        assert result[0].name == "Mokotów"
        assert result[0].is_selected is False

    def test_filters_out_unknown(self):
        api_data = [
            {"id": 1, "name_raw": "Mokotów", "name_normalized": "mokotow"},
            {"id": 2, "name_raw": "Unknown", "name_normalized": "unknown"},
        ]
        result = build_districts_from_api_response(api_data)

        assert len(result) == 1
        assert result[0].name == "Mokotów"

    def test_with_preselected_ids(self):
        api_data = [
            {"id": 1, "name_raw": "Mokotów", "name_normalized": "mokotow"},
            {"id": 2, "name_raw": "Ursynów", "name_normalized": "ursynow"},
        ]
        result = build_districts_from_api_response(api_data, selected_ids={1})

        assert result[0].is_selected is True
        assert result[1].is_selected is False

    def test_empty_input(self):
        result = build_districts_from_api_response([])
        assert result == []
