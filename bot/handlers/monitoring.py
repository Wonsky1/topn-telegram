import logging
from datetime import datetime
from typing import Optional

from aiogram import types
from aiogram.fsm.context import FSMContext

from bot.fsm import StartMonitoringForm, StatusForm, StopMonitoringForm
from bot.keyboards import (
    BACK_BUTTON,
    get_main_menu_keyboard,
    get_monitoring_selection_keyboard,
)
from bot.keyboards_inline import DistrictItem, build_districts_keyboard
from bot.responses import (
    BACK_TO_MENU,
    CHOOSE_MONITORING,
    DISTRICTS_FOUND,
    DUPLICATE_NAME,
    DUPLICATE_URL,
    ERROR_CREATING,
    ERROR_STOP,
    INVALID_NAME,
    INVALID_URL,
    MAIN_MENU,
    MONITORING_CREATED,
    MONITORING_CREATED_WITH_DISTRICTS,
    NO_MONITORINGS,
    RESERVED_NAME,
    SEND_NAME,
    SEND_URL,
    STOPPED,
    UNKNOWN_MONITORING,
    URL_NOT_REACHABLE,
)
from clients import topn_db_client
from core.dependencies import get_monitoring_service
from services.monitoring import MonitoringSpec
from services.validator import UrlValidator
from tools.url_parser import extract_city_from_olx_url

logger = logging.getLogger(__name__)


async def cmd_start_monitoring(message: types.Message, state: FSMContext):
    logger.info(
        f"Start monitoring questionnaire initiated by chat_id {message.chat.id}"
    )
    await state.set_state(StartMonitoringForm.url)
    kb = types.ReplyKeyboardMarkup(keyboard=[[BACK_BUTTON]], resize_keyboard=True)
    await message.answer(SEND_URL, reply_markup=kb)


async def process_url(message: types.Message, state: FSMContext):
    """Process URL input and optionally show district selection."""
    # Get the monitoring service from singleton container
    monitoring_service = get_monitoring_service()
    validator = UrlValidator()

    if message.text.strip() == BACK_BUTTON.text:
        keyboard = get_main_menu_keyboard(message.chat.id)
        await message.answer(BACK_TO_MENU, reply_markup=keyboard)
        await state.clear()
        return

    url = message.text.strip()
    if not validator.is_supported(url):
        await message.answer(INVALID_URL)
        return

    url = validator.normalize(url)
    if not validator.is_supported(url):
        await message.answer(INVALID_URL)
        return

    if not await validator.is_reachable(url):
        await message.answer(URL_NOT_REACHABLE)
        return

    # Check if URL is already monitored using the service
    try:
        if await monitoring_service._repo.has_url(str(message.chat.id), url):
            await message.answer(DUPLICATE_URL)
            return
    except Exception as e:
        logger.error(f"Error checking URL duplicate: {e}")
        await message.answer(ERROR_CREATING)
        return

    # Save URL to state
    await state.update_data(url=url)

    # Try to extract city from URL and offer district filtering
    city_slug = extract_city_from_olx_url(url)
    logger.info(f"Extracted city slug from URL: '{city_slug}'")

    if city_slug:
        city_data = await _try_get_city_with_districts(city_slug)
        logger.info(f"City data from DB: {city_data is not None}")

        if city_data:
            city_id = city_data["id"]
            city_name = city_data["name_raw"]
            districts_data = city_data.get("districts", [])

            # Filter out "Unknown" district
            districts_data = [
                d
                for d in districts_data
                if d.get("name_normalized", "").lower() != "unknown"
            ]

            if districts_data:
                # Save city info and districts to state
                await state.update_data(
                    city_id=city_id,
                    city_name=city_name,
                    districts_data=districts_data,
                    selected_district_ids=[],
                    districts_page=0,
                )

                # Build district keyboard
                districts = [
                    DistrictItem(id=d["id"], name=d["name_raw"]) for d in districts_data
                ]
                keyboard = build_districts_keyboard(districts, set(), 0)

                # Show district selection
                await state.set_state(StartMonitoringForm.districts)
                await message.answer(
                    DISTRICTS_FOUND.format(count=len(districts), city=city_name),
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
                return
            else:
                logger.info(f"No districts found for city '{city_name}'")
        else:
            logger.info(f"City '{city_slug}' not found in database")

    # No city found or no districts — proceed directly to name
    await state.set_state(StartMonitoringForm.name)
    kb = types.ReplyKeyboardMarkup(keyboard=[[BACK_BUTTON]], resize_keyboard=True)
    await message.answer(SEND_NAME, reply_markup=kb)


async def _try_get_city_with_districts(city_slug: str) -> Optional[dict]:
    """Try to get city with districts from API.

    Args:
        city_slug: Normalized city name (e.g., "warszawa")

    Returns:
        City dict with districts or None if not found
    """
    try:
        # First get city by normalized name
        logger.info(f"Looking up city by normalized name: '{city_slug}'")
        city = await topn_db_client.get_city_by_normalized_name(city_slug)

        if not city:
            logger.info(f"City '{city_slug}' not found in database")
            return None

        logger.info(f"Found city: id={city['id']}, name={city.get('name_raw')}")

        # Then get city with districts
        city_with_districts = await topn_db_client.get_city_with_districts(city["id"])
        districts_count = len(city_with_districts.get("districts", []))
        logger.info(f"City has {districts_count} districts")

        return city_with_districts
    except Exception as e:
        logger.error(f"Error fetching city '{city_slug}': {e}", exc_info=True)
        return None


async def process_name(message: types.Message, state: FSMContext):
    """Process name input and create monitoring task."""
    # Get the monitoring service from singleton container
    monitoring_service = get_monitoring_service()

    if message.text.strip() == BACK_BUTTON.text:
        keyboard = get_main_menu_keyboard(message.chat.id)
        await message.answer(BACK_TO_MENU, reply_markup=keyboard)
        await state.clear()
        return

    name = message.text.strip()
    if len(name) == 0 or len(name) > 64:
        await message.answer(INVALID_NAME)
        return

    data = await state.get_data()
    url = data["url"]

    # Get optional city and district data from state
    city_id: Optional[int] = data.get("city_id")
    selected_district_ids: list[int] = data.get("selected_district_ids", [])

    try:
        # Create monitoring spec with location filtering
        spec = MonitoringSpec(
            chat_id=str(message.chat.id),
            name=name,
            url=url,
            city_id=city_id,
            allowed_district_ids=(
                selected_district_ids if selected_district_ids else None
            ),
        )
        await monitoring_service.add_monitoring(spec)

        logger.info(
            f"Monitoring '{name}' created for chat_id {message.chat.id} "
            f"(city_id={city_id}, districts={len(selected_district_ids)})"
        )

        keyboard = get_main_menu_keyboard(message.chat.id)

        # Show appropriate success message
        if selected_district_ids:
            await message.answer(
                MONITORING_CREATED_WITH_DISTRICTS.format(
                    name=name,
                    url=url,
                    district_count=len(selected_district_ids),
                ),
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        else:
            await message.answer(
                MONITORING_CREATED.format(name=name, url=url),
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
    except ValueError as e:
        # Handle validation errors from the service
        error_msg = str(e)
        if "Duplicate URL" in error_msg:
            await message.answer(DUPLICATE_URL)
        elif "Duplicate name" in error_msg:
            await message.answer(DUPLICATE_NAME)
        elif "Unsupported URL" in error_msg:
            await message.answer(INVALID_URL)
        elif "URL not reachable" in error_msg:
            await message.answer(URL_NOT_REACHABLE)
        else:
            await message.answer(INVALID_NAME)
    except Exception as e:
        logger.error(f"Error creating monitoring: {e}", exc_info=True)
        await message.answer(ERROR_CREATING)

    await state.clear()


# -------------------- STOP MONITORING --------------------


async def stop_monitoring_command(message: types.Message, state: FSMContext):
    """Ask user which monitoring to stop."""
    monitoring_service = get_monitoring_service()

    try:
        tasks = await monitoring_service.list_monitorings(str(message.chat.id))
        if not tasks:
            await message.answer(
                "📋 *No active monitoring found*\n\nYou don't have any monitoring tasks set up.\nStart your monitoring to begin monitoring.",
                parse_mode="Markdown",
            )
            return
        kb = get_monitoring_selection_keyboard([t.name for t in tasks])
        await message.answer("Choose monitoring to stop:", reply_markup=kb)
        await state.set_state(StopMonitoringForm.choosing)
    except Exception as e:
        logger.error(f"Error listing tasks for stop: {e}")
        await message.answer(ERROR_STOP)


async def process_stop_choice(message: types.Message, state: FSMContext):
    """Handle user's selection and delete monitoring."""
    monitoring_service = get_monitoring_service()

    name = message.text.strip()
    if name == BACK_BUTTON.text:
        # Go back to main menu
        keyboard = get_main_menu_keyboard(message.chat.id)
        await message.answer("Back to main menu", reply_markup=keyboard)
        await state.clear()
        return

    # Prevent stopping reserved names
    if name.startswith("/"):
        await message.answer(RESERVED_NAME)
        return

    try:
        await monitoring_service.remove_monitoring(str(message.chat.id), name)
        logger.info(f"Monitoring '{name}' deleted for chat_id {message.chat.id}")
        keyboard = get_main_menu_keyboard(message.chat.id)
        await message.answer(
            STOPPED.format(name=name),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    except ValueError as e:
        if "not found" in str(e).lower():
            await message.answer(UNKNOWN_MONITORING)
        else:
            await message.answer(ERROR_STOP)
    except Exception as e:
        logger.error(f"Error deleting monitoring: {e}", exc_info=True)
        await message.answer(ERROR_STOP)

    await state.clear()


# -------------------- STATUS --------------------


async def status_command(message: types.Message, state: FSMContext):
    """Show status or ask user to choose if multiple monitorings."""
    monitoring_service = get_monitoring_service()

    try:
        tasks = await monitoring_service.list_monitorings(str(message.chat.id))
        if not tasks:
            await message.answer(NO_MONITORINGS, parse_mode="Markdown")
            return

        if len(tasks) == 1:
            await _send_status(message, tasks[0])
        else:
            kb = get_monitoring_selection_keyboard([t.name for t in tasks])
            await message.answer(CHOOSE_MONITORING, reply_markup=kb)
            await state.set_state(StatusForm.choosing)
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        await message.answer("Error retrieving monitoring status.")


async def process_status_choice(message: types.Message, state: FSMContext):
    monitoring_service = get_monitoring_service()

    name = message.text.strip()
    if name == BACK_BUTTON.text:
        keyboard = get_main_menu_keyboard(message.chat.id)
        await message.answer("Back to main menu", reply_markup=keyboard)
        await state.clear()
        return

    try:
        tasks = await monitoring_service.list_monitorings(str(message.chat.id))
        task = next((t for t in tasks if t.name == name), None)

        if task:
            await _send_status(message, task)
            keyboard = get_main_menu_keyboard(message.chat.id)
            await message.answer(MAIN_MENU, reply_markup=keyboard)
        else:
            await message.answer(UNKNOWN_MONITORING)
            return
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        await message.answer("Error retrieving monitoring status.")

    await state.clear()


async def _send_status(message: types.Message, task):
    status_text = (
        f"✅ *Monitoring is ACTIVE*\n\n"
        f"📛 *Name:* {task.name}\n"
        f"🔗 *URL:* [View link]({task.url})\n"
    )

    # Handle datetime formatting safely
    def format_datetime(dt_value):
        if not dt_value:
            return "Never"

        # If it's already a datetime object
        if hasattr(dt_value, "strftime"):
            return dt_value.strftime("%Y-%m-%d %H:%M:%S")

        # If it's an ISO string, parse it
        if isinstance(dt_value, str):
            try:
                # Parse ISO format string
                dt = datetime.fromisoformat(dt_value.replace("Z", "+00:00"))
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                return str(dt_value)

        return str(dt_value)

    status_text += f"🕒 *Last updated:* {format_datetime(task.last_updated)}\n"
    status_text += f"📦 *Last item sent:* {format_datetime(task.last_got_item)}\n"

    await message.answer(status_text, parse_mode="Markdown")
