# Architecture

Telegram Message Tracker is built around Telegram Business updates.

## Main flow

1. Telegram sends a business update to the bot
2. The bot receives the message
3. Message data is stored temporarily
4. Edited or deleted messages are detected
5. The previous message state is sent back to the user

## Storage

The project supports:

- Local file storage
- Redis for persistent cloud storage

## Deployment

The bot can run using:

- Long polling
- Webhooks
- Railway
- Render

## Main components

- Telegram Bot API
- python-telegram-bot
- Redis
- aiohttp
- Docker
