from aiogram import types

from core.config import settings


def get_main_menu_keyboard(chat_id: int) -> types.ReplyKeyboardMarkup:
    """Get main menu keyboard, with admin panel button for admins."""
    keyboard = [
        [
            types.KeyboardButton(text="Start monitoring"),
            types.KeyboardButton(text="Stop monitoring"),
        ],
        [types.KeyboardButton(text="Status")],
    ]

    # Add admin panel button for admins
    if settings.is_admin(chat_id):
        keyboard.append([types.KeyboardButton(text="🔧 Admin Panel")])

    return types.ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Start, stop monitoring, or check status",
    )


BACK_BUTTON = types.KeyboardButton(text="⬅️ Back")


def get_monitoring_selection_keyboard(names: list[str]) -> types.ReplyKeyboardMarkup:
    kb = [[types.KeyboardButton(text=n)] for n in names]
    kb.append([BACK_BUTTON])
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_admin_panel_keyboard() -> types.ReplyKeyboardMarkup:
    """Get admin panel keyboard with all admin options."""
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(text="📊 System Status"),
                types.KeyboardButton(text="👥 View Users"),
            ],
            [
                types.KeyboardButton(text="📋 View All Tasks"),
                types.KeyboardButton(text="⚠️ Recent Errors"),
            ],
            [types.KeyboardButton(text="⬅️ Back to Menu")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Admin Panel",
    )
