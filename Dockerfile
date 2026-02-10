FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv (to system Python)
RUN uv sync --frozen --no-dev

COPY . .

ARG BOT_TOKEN
ARG ADMIN_IDS
ARG REDIS_HOST
ARG REDIS_PORT
ARG TOPN_DB_BASE_URL

ENV BOT_TOKEN=${BOT_TOKEN}
ENV ADMIN_IDS=${ADMIN_IDS}
ENV REDIS_HOST=${REDIS_HOST}
ENV REDIS_PORT=${REDIS_PORT}
ENV TOPN_DB_BASE_URL=${TOPN_DB_BASE_URL}

CMD ["uv", "run", "main.py"]
