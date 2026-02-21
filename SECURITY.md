# Security Policy

## Reporting a vulnerability

Please report security issues privately by emailing the project owner.
Do not open a public issue for security-sensitive reports.

## Supported versions

This project is in early development. Only the latest commit is supported.

## Best practices (current)

- Keep `.env` out of Git and rotate secrets if exposed.
- Use least-privilege DB users for production.
- Store production secrets in the hosting provider’s secret manager.
