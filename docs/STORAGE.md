# Storage

Telegram Message Tracker supports two ways to store application state.

## Local Storage

By default, the bot can store state in:

`state.json`

This is useful for local development.

The file is excluded from Git through `.gitignore`.

## Redis

Redis can be used for persistent storage on cloud platforms.

Configure it using:

`REDIS_URL`

Redis is recommended when the local filesystem does not persist between deployments.

## Security

Never commit:

- Redis credentials
- `state.json`
- `.env`
- private user data
