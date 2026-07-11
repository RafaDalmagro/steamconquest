FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Dependências primeiro (camada cacheável); app depois.
COPY pyproject.toml uv.lock ./
COPY app ./app
RUN uv sync --frozen --no-dev

# Roda como usuário não-root (hardening).
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Worker único: o TTLCache é estado em processo (ver CLAUDE.md / spec INF-001).
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
