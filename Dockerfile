FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Dependencies first — cached unless pyproject.toml or uv.lock changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code
COPY ui/ ./ui/
COPY scripts/ ./scripts/
COPY models/ ./models/

RUN uv sync --frozen --no-dev

EXPOSE 8767

CMD ["uv", "run", "shiny", "run", "ui/app.py", "--host", "0.0.0.0", "--port", "8767"]
