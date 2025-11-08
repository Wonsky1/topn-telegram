# telegram_service.py
import asyncio
import logging
from logging.handlers import TimedRotatingFileHandler

import redis.asyncio as redis
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.redis import RedisStorage

from bot.fsm import StartMonitoringForm, StatusForm, StopMonitoringForm
from bot.handlers import monitoring as monitoring_handlers
from bot.keyboards import MAIN_MENU_KEYBOARD
from core.config import settings
from core.dependencies import get_monitoring_service, get_repository

# Dependency injection – business & infrastructure layers
from services.notifier import Notifier

file_handler = TimedRotatingFileHandler(
    filename="bot.log",
    when="midnight",  # Rotate at midnight
    interval=1,  # Every day
    backupCount=30,  # Keep 30 days (approximately 1 month)
    encoding="utf-8",
)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        file_handler,
    ],
)
logger = logging.getLogger(__name__)

redis_client = redis.Redis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True
)
storage = RedisStorage(redis_client)
dp = Dispatcher(storage=storage)


async def telegram_main():
    # Initialize bot
    logger.info("Initializing bot")
    bot = Bot(token=settings.BOT_TOKEN)

    # Get services from singleton container
    mon_service = get_monitoring_service()
    repo = get_repository()
    notifier = Notifier(bot, mon_service, redis_client)

    # Register FSM handlers
    dp.message.register(
        monitoring_handlers.cmd_start_monitoring, Command(commands=["start_monitoring"])
    )
    dp.message.register(monitoring_handlers.process_url, StartMonitoringForm.url)
    dp.message.register(monitoring_handlers.process_name, StartMonitoringForm.name)
    dp.message.register(monitoring_handlers.process_status_choice, StatusForm.choosing)
    dp.message.register(
        monitoring_handlers.process_stop_choice, StopMonitoringForm.choosing
    )

    # Command handlers
    @dp.message(CommandStart())
    async def cmd_start(message: types.Message):
        logger.info(f"Start command received from chat_id {message.chat.id}")
        await message.answer(
            "Hello Yana, this is a bot for you <3", reply_markup=MAIN_MENU_KEYBOARD
        )

    # Text button handlers
    @dp.message(lambda message: message.text == "Start monitoring")
    async def start_monitoring_button(message: types.Message, state: FSMContext):
        await monitoring_handlers.cmd_start_monitoring(message, state)

    @dp.message(lambda message: message.text == "Stop monitoring")
    async def stop_monitoring_button(message: types.Message, state: FSMContext):
        await monitoring_handlers.stop_monitoring_command(message, state)

    @dp.message(lambda message: message.text == "Status")
    async def status_button(message: types.Message, state: FSMContext):
        await monitoring_handlers.status_command(message, state)

    # Start periodic check for new items
    logger.info("Starting periodic check for new items...")
    asyncio.create_task(notifier.run_periodically(settings.CHECK_FREQUENCY_SECONDS))
    asyncio.create_task(
        repo.remove_old_items_data_infinitely(settings.DB_REMOVE_OLD_ITEMS_DATA_N_DAYS)
    )

    # Start polling
    logger.info("Starting bot polling...")
    chat_id = settings.CHAT_IDS
    try:
        await bot.send_message(chat_id=chat_id, text="BOT WAS STARTED")
        logger.info(f"Bot started notification sent to chat_id {chat_id}")
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Fatal error in telegram_main: {e}", exc_info=True)
    finally:
        logger.info("Bot stopped, sending notification")
        await bot.send_message(chat_id=chat_id, text="BOT WAS STOPPED")


if __name__ == "__main__":
    logger.info("Starting telegram service...")
    asyncio.run(telegram_main())
