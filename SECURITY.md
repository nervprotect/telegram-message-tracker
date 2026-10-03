# Security Policy

## Reporting a Security Issue

Please do not publish sensitive information such as:

- Telegram bot tokens
- Redis credentials
- API keys
- User data

If you discover a security issue, avoid including credentials or private data in public issues.

## Credentials

All secrets should be stored using environment variables.

Never commit `.env` files or real credentials to the repository.
