FROM python:3.11-slim

# Копируем бинарник uv из официального образа (самый надежный способ)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Копируем файлы зависимостей
COPY pyproject.toml uv.lock ./

# Устанавливаем зависимости
# --frozen гарантирует точное соответствие версий из uv.lock
RUN uv sync --frozen

# Копируем исходный код
COPY . .

# Порты
EXPOSE 8000 8501

# CMD переопределяется в docker-compose
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]