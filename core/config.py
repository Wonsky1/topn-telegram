"""Define configuration settings using Pydantic and manage environment variables."""

from logging import getLogger

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = getLogger(__name__)


class Settings(BaseSettings):
    """Class defining configuration settings using Pydantic."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True
    )

    BOT_TOKEN: str
    ADMIN_IDS: str = ""  # Comma-separated list of admin chat IDs

    CHECK_FREQUENCY_SECONDS: int = 10

    TOPN_DB_BASE_URL: str

    # DB settings
    DB_REMOVE_OLD_ITEMS_DATA_N_DAYS: int = 7
    # Image cache TTL (in days) - should match DB_REMOVE_OLD_ITEMS_DATA_N_DAYS
    IMAGE_CACHE_TTL_DAYS: int = DB_REMOVE_OLD_ITEMS_DATA_N_DAYS + 1

    # Redis settings for state persistence
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    def get_admin_ids(self) -> list[str]:
        """Parse and return list of admin IDs."""
        if not self.ADMIN_IDS:
            return []
        return [
            admin_id.strip()
            for admin_id in self.ADMIN_IDS.split(",")
            if admin_id.strip()
        ]

    def is_admin(self, chat_id: int | str) -> bool:
        """Check if the given chat_id is an admin."""
        return str(chat_id) in self.get_admin_ids()


settings = Settings()
