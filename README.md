#  async Telegram Bot made for flats search

Sends messages to mentioned accounts with new flats posted on olx.pl

## Features

- 🏠 Monitor OLX listings for new apartments/flats
- 📱 Real-time Telegram notifications with images
- 🔄 Automatic periodic checking
- 💾 Smart image caching
- 🔧 **Admin Panel** for system monitoring and management

## Environment Variables

Required environment variables:

```bash
BOT_TOKEN=your_bot_token
ADMIN_IDS=admin_chat_ids  # comma-separated list for admin access
REDIS_HOST=redis
REDIS_PORT=6379
TOPN_DB_BASE_URL=http://db:8000
CHECK_FREQUENCY_SECONDS=10  # Optional: default is 10
DB_REMOVE_OLD_ITEMS_DATA_N_DAYS=7  # Optional: default is 7
```

## Admin Panel

Administrators can access a powerful admin panel directly in Telegram. See [ADMIN_PANEL_README.md](ADMIN_PANEL_README.md) for details.

Features include:
- 📊 System status monitoring
- 👥 User management
- 📋 Task overview
- ⚠️ Error logs

To enable admin access, add your Telegram chat ID to `ADMIN_IDS` environment variable.

## Documentation

- [Admin Panel Guide](ADMIN_PANEL_README.md) - Complete admin panel documentation
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md) - Technical implementation details
- [Bugs & Improvements](BUGS-AND-IMPROVEMENTS-README.md) - Feature roadmap
