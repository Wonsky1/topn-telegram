"""Admin panel handlers for bot management and monitoring."""

import logging
import time
from datetime import datetime, timedelta

import psutil
from aiogram import types
from aiogram.fsm.context import FSMContext

from bot.keyboards import get_admin_panel_keyboard, get_main_menu_keyboard
from core.config import settings
from core.dependencies import get_monitoring_service, get_repository

logger = logging.getLogger(__name__)

# Track bot start time
BOT_START_TIME = time.time()


def is_admin(chat_id: int) -> bool:
    """Check if user is admin."""
    return settings.is_admin(chat_id)


async def admin_panel_menu(message: types.Message, state: FSMContext):
    """Show admin panel main menu."""
    if not is_admin(message.chat.id):
        await message.answer(
            "⛔ Access denied. This feature is for administrators only."
        )
        return

    await state.clear()
    keyboard = get_admin_panel_keyboard()
    await message.answer(
        "🔧 *Admin Panel*\n\n" "Welcome to the admin panel. Choose an option below:",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def system_status(message: types.Message, state: FSMContext):
    """Show system status and health information."""
    if not is_admin(message.chat.id):
        await message.answer("⛔ Access denied.")
        return

    await message.answer("⏳ Gathering system information...")

    try:
        # Get services
        get_monitoring_service()
        repo = get_repository()

        # Bot uptime
        uptime_seconds = time.time() - BOT_START_TIME
        uptime_delta = timedelta(seconds=int(uptime_seconds))

        # Get all tasks
        all_tasks_response = await repo._client.get_all_tasks()
        all_tasks = all_tasks_response.get("tasks", [])
        active_tasks = [t for t in all_tasks if t.get("is_active", True)]

        # Get unique users
        unique_users = set(t.get("chat_id") for t in all_tasks if t.get("chat_id"))

        # Get pending tasks
        pending_tasks_response = await repo._client.get_pending_tasks()
        pending_tasks = pending_tasks_response.get("tasks", [])

        # System resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # Database health
        try:
            await repo._client.health_check()
            db_status = "✅ Healthy"
        except Exception as e:
            db_status = f"❌ Error: {str(e)[:50]}"

        # Redis health
        try:
            from core.dependencies import redis_client

            await redis_client.ping()
            redis_status = "✅ Connected"
            redis_keys = await redis_client.dbsize()
            photo_keys = await redis_client.keys("photo:*")
            redis_info = f" ({redis_keys} keys, {len(photo_keys)} cached images)"
        except Exception as e:
            redis_status = f"❌ Error: {str(e)[:50]}"
            redis_info = ""

        # Calculate actual memory percentage (used/total)
        memory_used_gb = round(memory.used / (1024**3), 2)
        memory_total_gb = round(memory.total / (1024**3), 2)
        memory_percent_actual = round((memory.used / memory.total) * 100, 1)

        disk_used_gb = round(disk.used / (1024**3), 2)
        disk_total_gb = round(disk.total / (1024**3), 2)
        disk_percent_actual = round((disk.used / disk.total) * 100, 1)

        # Format status message
        status_text = (
            "📊 *System Status*\n\n"
            f"🤖 *Bot Status:* Running\n"
            f"⏱ *Uptime:* {uptime_delta}\n"
            f"🕐 *Started:* {datetime.fromtimestamp(BOT_START_TIME).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"👥 *Users:* {len(unique_users)}\n"
            f"📋 *Total Tasks:* {len(all_tasks)}\n"
            f"✅ *Active Tasks:* {len(active_tasks)}\n"
            f"⏳ *Pending Checks:* {len(pending_tasks)}\n\n"
            f"🗄 *Database:* {db_status}\n"
            f"💾 *Redis:* {redis_status}{redis_info}\n\n"
            f"💻 *CPU Usage:* {cpu_percent}%\n"
            f"🧠 *Memory:* {memory_percent_actual}% ({memory_used_gb}GB / {memory_total_gb}GB)\n"
            f"💿 *Disk:* {disk_percent_actual}% ({disk_used_gb}GB / {disk_total_gb}GB)\n\n"
            f"⚙️ *Check Frequency:* {settings.CHECK_FREQUENCY_SECONDS}s\n"
            f"🗑 *Data Retention:* {settings.DB_REMOVE_OLD_ITEMS_DATA_N_DAYS} days"
        )

        await message.answer(status_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error getting system status: {e}", exc_info=True)
        await message.answer(f"❌ Error getting system status: {str(e)}")


async def view_all_users(message: types.Message, state: FSMContext):
    """Show all users and their monitoring tasks."""
    if not is_admin(message.chat.id):
        await message.answer("⛔ Access denied.")
        return

    await message.answer("⏳ Loading users...")

    try:
        repo = get_repository()
        all_tasks_response = await repo._client.get_all_tasks()
        all_tasks = all_tasks_response.get("tasks", [])

        # Group tasks by user
        users_tasks = {}
        for task in all_tasks:
            chat_id = task.get("chat_id")
            if chat_id:
                if chat_id not in users_tasks:
                    users_tasks[chat_id] = []
                users_tasks[chat_id].append(task)

        if not users_tasks:
            await message.answer("📋 No users found.")
            return

        # Format user list
        user_list = "👥 *All Users*\n\n"
        for idx, (chat_id, tasks) in enumerate(users_tasks.items(), 1):
            active_count = len([t for t in tasks if t.get("is_active", True)])
            user_list += f"{idx}\\. *User:* `{chat_id}`\n"
            user_list += f"   📋 Tasks: {len(tasks)} \\({active_count} active\\)\n\n"

            if idx >= 20:  # Limit to 20 users per message
                user_list += f"_\\.\\.\\. and {len(users_tasks) - 20} more users_"
                break

        await message.answer(user_list, parse_mode="MarkdownV2")

    except Exception as e:
        logger.error(f"Error viewing users: {e}", exc_info=True)
        await message.answer(f"❌ Error: {str(e)}")


async def view_all_tasks(message: types.Message, state: FSMContext):
    """Show all monitoring tasks across all users."""
    if not is_admin(message.chat.id):
        await message.answer("⛔ Access denied.")
        return

    await message.answer("⏳ Loading tasks...")

    try:
        repo = get_repository()
        all_tasks_response = await repo._client.get_all_tasks()
        all_tasks = all_tasks_response.get("tasks", [])

        if not all_tasks:
            await message.answer("📋 No monitoring tasks found.")
            return

        # Sort by last_updated (most recent first)
        all_tasks.sort(key=lambda t: t.get("last_updated", ""), reverse=True)

        # Format task list
        task_list = f"📋 *All Monitoring Tasks* \\({len(all_tasks)} total\\)\n\n"

        for idx, task in enumerate(all_tasks[:15], 1):  # Show first 15
            name = task.get("name", "Unknown")
            chat_id = task.get("chat_id", "N/A")
            is_active = "✅" if task.get("is_active", True) else "❌"
            last_updated = task.get("last_updated", "Never")

            # Format timestamp
            if last_updated and last_updated != "Never":
                try:
                    dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                    last_updated = dt.strftime("%m/%d %H:%M")
                except:
                    pass

            # Escape special characters for MarkdownV2
            name_escaped = (
                name.replace("_", "\\_")
                .replace("*", "\\*")
                .replace("[", "\\[")
                .replace("]", "\\]")
                .replace("(", "\\(")
                .replace(")", "\\)")
                .replace("~", "\\~")
                .replace("`", "\\`")
                .replace(">", "\\>")
                .replace("#", "\\#")
                .replace("+", "\\+")
                .replace("-", "\\-")
                .replace("=", "\\=")
                .replace("|", "\\|")
                .replace("{", "\\{")
                .replace("}", "\\}")
                .replace(".", "\\.")
                .replace("!", "\\!")
            )
            chat_id_escaped = (
                str(chat_id)
                .replace("_", "\\_")
                .replace("*", "\\*")
                .replace("[", "\\[")
                .replace("]", "\\]")
                .replace("(", "\\(")
                .replace(")", "\\)")
                .replace("~", "\\~")
                .replace("`", "\\`")
                .replace(">", "\\>")
                .replace("#", "\\#")
                .replace("+", "\\+")
                .replace("-", "\\-")
                .replace("=", "\\=")
                .replace("|", "\\|")
                .replace("{", "\\{")
                .replace("}", "\\}")
                .replace(".", "\\.")
                .replace("!", "\\!")
            )
            last_updated_escaped = (
                str(last_updated)
                .replace("_", "\\_")
                .replace("*", "\\*")
                .replace("[", "\\[")
                .replace("]", "\\]")
                .replace("(", "\\(")
                .replace(")", "\\)")
                .replace("~", "\\~")
                .replace("`", "\\`")
                .replace(">", "\\>")
                .replace("#", "\\#")
                .replace("+", "\\+")
                .replace("-", "\\-")
                .replace("=", "\\=")
                .replace("|", "\\|")
                .replace("{", "\\{")
                .replace("}", "\\}")
                .replace(".", "\\.")
                .replace("!", "\\!")
            )

            task_list += f"{idx}\\. {is_active} *{name_escaped}*\n"
            task_list += f"   👤 User: `{chat_id_escaped}`\n"
            task_list += f"   🕐 Updated: {last_updated_escaped}\n\n"

        if len(all_tasks) > 15:
            task_list += f"_\\.\\.\\. and {len(all_tasks) - 15} more tasks_"

        await message.answer(task_list, parse_mode="MarkdownV2")

    except Exception as e:
        logger.error(f"Error viewing tasks: {e}", exc_info=True)
        await message.answer(f"❌ Error: {str(e)}")


async def view_recent_errors(message: types.Message, state: FSMContext):
    """Show recent errors from logs."""
    if not is_admin(message.chat.id):
        await message.answer("⛔ Access denied.")
        return

    try:
        errors = []
        with open("bot.log", "r") as f:
            lines = f.readlines()

        # Get last 20 error lines
        for line in reversed(lines[-500:]):  # Check last 500 lines
            if "ERROR" in line or "CRITICAL" in line:
                errors.append(line.strip())
                if len(errors) >= 20:
                    break

        if not errors:
            await message.answer("✅ No recent errors found!")
            return

        error_text = f"⚠️ *Recent Errors* ({len(errors)})\n\n"
        for idx, error in enumerate(errors, 1):
            # Truncate long errors
            if len(error) > 150:
                error = error[:150] + "..."
            error_text += f"{idx}. `{error}`\n\n"

        # Split into chunks if too long
        if len(error_text) > 4000:
            error_text = error_text[:4000] + "\n\n_... truncated_"

        await message.answer(error_text, parse_mode="Markdown")

    except FileNotFoundError:
        await message.answer("📋 No log file found.")
    except Exception as e:
        logger.error(f"Error reading logs: {e}", exc_info=True)
        await message.answer(f"❌ Error reading logs: {str(e)}")


async def back_to_main_menu(message: types.Message, state: FSMContext):
    """Return to main menu."""
    await state.clear()
    keyboard = get_main_menu_keyboard(message.chat.id)
    await message.answer("Back to main menu", reply_markup=keyboard)
