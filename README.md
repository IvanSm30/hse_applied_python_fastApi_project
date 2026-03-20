# General

Приложение поднято на виртуальной машине и расположено по адресу:  `http://185.70.105.233:8000/docs`

# Dev mode
### FastAPI App

1. `curl -LsSf https://astral.sh/uv/install.sh | sh` - macos, `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` - windows;
2. `uv sync`;
3. `source .venv/bin/activate` – macos, `.venv\Scripts\activate` – windows;
4. `uv run uvicorn main:app --reload`.

# Prod mode
### FastAPI App

1. `docker-compose up --build`

## Реализованные методы

- `POST /links/shorten` — создать короткую ссылку (+ custom_alias)
- `GET /{short_code}` — редирект на оригинал
- `DELETE /links/{short_code}` — удалить ссылку
- `PUT /links/{short_code}` — обновить ссылку
- `GET /links/{short_code}/stats` — статистика переходав

## Особенности

- Кэширование в Redis
- Custom alias (свой короткий код)
- Поиск по original_url
- Поле expires_at (срок жизни ссылки)
- Docker Compose + Healthchecks
- PostgreSQL