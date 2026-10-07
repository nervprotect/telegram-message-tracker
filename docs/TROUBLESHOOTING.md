# Troubleshooting

## Bot does not respond

Check that:

- `BOT_TOKEN` is configured correctly
- The bot is running
- Telegram Business is connected

## Admin commands do not work

Make sure `ADMIN_ID` is configured correctly.

## State disappears after restart

Use persistent storage:

- Railway Volume
- Redis for cloud deployments

## Redis connection fails

Check that `REDIS_URL` is valid and accessible.

## Deployment problems

Check the service logs on Railway or Render for errors.
