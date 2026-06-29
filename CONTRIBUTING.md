# Contributing

## Development

Use Docker Compose for the supported development environment:

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up --build -d
docker compose -f docker-compose.dev.yml exec backend alembic upgrade head
```

## Checks

Run the focused checks before opening a change:

```bash
docker compose -f docker-compose.dev.yml exec backend pytest
docker compose -f docker-compose.dev.yml exec frontend npm run type-check
docker compose -f docker-compose.dev.yml exec frontend npm run lint
```

## Code Guidelines

- Keep backend business rules in application/domain layers when possible.
- Keep SQLAlchemy models and external services in infrastructure.
- Preserve organization scoping on every business query.
- Add migrations for schema changes and tests for permission or money logic.
- Do not commit generated caches, local `.env` files, or build artifacts.
