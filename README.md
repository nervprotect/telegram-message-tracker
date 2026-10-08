# Telegram Message Tracker

A Telegram bot that tracks deleted and edited messages using Telegram Business.

## Features

- Saves messages before they are deleted
- Sends deleted message content back to the user
- Detects edited messages
- Shows original and edited message versions
- Telegram Business integration
- Redis persistence
- Webhook support
- Docker deployment


## 🔍 How It Works

Telegram Message Tracker works through Telegram Business connections.

When a message is received, the bot stores its data temporarily. If the message is later deleted or edited, the bot can show the previous version to the user.

The bot supports persistent storage with Redis for cloud deployments.

## Tech Stack

- Python
- python-telegram-bot
- Redis
- aiohttp
- Docker

## ⚙️ Configuration

The project uses environment variables for configuration.

See `.env.example` for the required variables:

- `BOT_TOKEN` — Telegram bot token
- `ADMIN_ID` — Telegram administrator user ID
- `DATA_DIR` — directory for local state storage
- `REDIS_URL` — Redis connection URL

## Deployment

Supports deployment on:

- Railway
- Render

## 📚 Documentation

- [Commands](docs/COMMANDS.md)
- [FAQ](FAQ.md)
- [Security](SECURITY.md)
- [Privacy](PRIVACY.md)
- [Support](SUPPORT.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)

## 🗺 Roadmap

- [ ] Add automated tests (#1)
- [ ] Improve error handling (#5)
- [ ] Add GitHub Actions CI (#3)
- [ ] Improve logging (#2)
- [ ] Support more message types (#4)


## ⚠️ Limitations

- The bot can only track messages received while it is connected
- Messages deleted before the bot receives them cannot be recovered
- Some Telegram message types may not be fully supported yet
- Telegram Business must be enabled for the bot
