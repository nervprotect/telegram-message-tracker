# Privacy

Telegram Message Tracker processes message data required for its tracking features.

## Sensitive Data

Do not store or publish:

- Bot tokens
- Redis credentials
- API keys
- Private `.env` files
- User message data

## Configuration

Secrets should be stored using environment variables and must not be committed to the repository.

## Reporting

If sensitive information is accidentally exposed, remove it and rotate the affected credentials immediately.
