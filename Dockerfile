# Trading Agent — Dockerfile
# Build:  docker build -t kay/trading-agent:latest .
# Run:    docker compose up -d

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Berlin

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone

# Python dependencies (core — faster-whisper added separately if needed)
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Copy application code (host vault/ is gitignored — not copied here)
COPY trading_agent/    trading_agent/
COPY dashboard/        dashboard/
COPY scripts/          scripts/
COPY quiz/             quiz/
COPY knowledge/        knowledge/
COPY docs/             docs/
COPY config/           config/

# Entrypoint: loads env vars into vault → starts cron + live loop + dashboard
COPY scripts/docker_entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh

EXPOSE 5050
ENTRYPOINT ["/entrypoint.sh"]
