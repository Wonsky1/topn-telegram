import logging
from datetime import datetime

from aiogram import types
from aiogram.fsm.context import FSMContext

from bot.fsm import StartMonitoringForm, StatusForm, StopMonitoringForm
from bot.keyboards import (
    BACK_BUTTON,
    get_main_menu_keyboard,
    get_monitoring_selection_keyboard,
)
from bot.responses import (
    BACK_TO_MENU,
    CHOOSE_MONITORING,
    DUPLICATE_NAME,
    DUPLICATE_URL,
    ERROR_CREATING,
    ERROR_STOP,
    INVALID_NAME,
    INVALID_URL,
    MAIN_MENU,
    MONITORING_CREATED,
    NO_MONITORINGS,
    RESERVED_NAME,
    SEND_NAME,
    SEND_URL,
    STOPPED,
    UNKNOWN_MONITORING,
    URL_NOT_REACHABLE,
)
from core.dependencies import get_monitoring_service
from services.monitoring import MonitoringSpec
from services.validator import UrlValidator

logger = logging.getLogger(__name__)


async def cmd_start_monitoring(message: types.Message, state: FSMContext):
    logger.info(
        f"Start monitoring questionnaire initiated by chat_id {message.chat.id}"
    )
    await state.set_state(StartMonitoringForm.url)
    kb = types.ReplyKeyboardMarkup(keyboard=[[BACK_BUTTON]], resize_keyboard=True)
    await message.answer(SEND_URL, reply_markup=kb)


async def process_url(message: types.Message, state: FSMContext):
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

    await state.update_data(url=url)
    await state.set_state(StartMonitoringForm.name)
    kb = types.ReplyKeyboardMarkup(keyboard=[[BACK_BUTTON]], resize_keyboard=True)
    await message.answer(SEND_NAME, reply_markup=kb)


async def process_name(message: types.Message, state: FSMContext):
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

    try:
        # Create monitoring spec and add it using the service
        spec = MonitoringSpec(chat_id=str(message.chat.id), name=name, url=url)
        await monitoring_service.add_monitoring(spec)

        logger.info(f"Monitoring '{name}' created for chat_id {message.chat.id}")
        keyboard = get_main_menu_keyboard(message.chat.id)
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
