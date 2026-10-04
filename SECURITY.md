# Security Policy

## Reporting a Security Issue

If you discover a security vulnerability, please do not publish sensitive details in a public issue.

When reporting a security problem:

- Do not include bot tokens
- Do not include Redis credentials
- Do not include API keys
- Do not include private user data
- Describe the issue without exposing active credentials

## Secrets

All secrets must be stored using environment variables.

Never commit:

- `.env`
- bot tokens
- Redis passwords
- API keys
- other private credentials

If a secret is accidentally exposed, revoke or rotate it immediately.

## Repository Safety

Before committing changes, make sure no sensitive data is included in:

- source code
- logs
- screenshots
- configuration files
- issue descriptions
