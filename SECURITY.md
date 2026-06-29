# Security Policy

## Reporting a Vulnerability

Please report suspected vulnerabilities privately to the project maintainers.
Do not open public issues for secrets exposure, authentication bypasses, data
isolation issues, payment issues, or remote code execution risks.

Include:

- A short description of the issue.
- Steps to reproduce.
- Expected impact.
- Affected environment, commit, or deployment.

## Supported Version

Security fixes target the `main` branch unless a maintained release branch is
explicitly documented.

## Secrets

Never commit `.env`, production credentials, API keys, database dumps, customer
documents, or generated private certificates. Rotate any secret that may have
been exposed locally or in CI logs.
