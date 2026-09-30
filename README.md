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

## 🗺 Roadmap

- [ ] Add automated tests(#1)
- [ ] Improve error handling
- [ ] Add GitHub Actions CI
- [ ] Improve logging
- [ ] Support more message types



