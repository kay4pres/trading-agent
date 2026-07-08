FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Berlin
ENV PYTHONPATH=/app

WORKDIR /app

# Install system deps + Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron tzdata unzip git \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && pip install --no-cache-dir --break-system-packages \
        Flask flask-cors yfinance requests "python-telegram-bot>=20.7" croniter pandas numpy \
        tradingview-screener

# Build arguments
ARG GIT_REF=main
ARG CACHEBUST=20260708
# GITEA_TOKEN: bearer token for authenticated clone from Gitea (optional)
# If provided, clones from Gitea. Otherwise falls back to GitHub public download.
ARG GITEA_TOKEN=

# Primary: clone from Gitea (private repo) with auth token
# Fallback: download from GitHub (public) if GITEA_TOKEN is empty
RUN if [ -n "$GITEA_TOKEN" ]; then \
        echo "Cloning from Gitea..." && \
        git clone --depth=1 --branch=${GIT_REF} \
            http://kay:${GITEA_TOKEN}@10.8.0.10:3000/trading/trading-agent.git /app; \
    else \
        echo "Cloning from GitHub (public)..." && \
        unzip -q https://github.com/kay4pres/trading-agent/archive/refs/heads/${GIT_REF}.zip -d /tmp && \
        mv /tmp/trading-agent-${GIT_REF}/* /app/ && \
        rm -rf /tmp/trading-agent-${GIT_REF}; \
    fi \
    && rm -rf /app/.git \
    && pip install --no-cache-dir --break-system-packages -r /app/requirements.txt \
    && chmod +x /app/entrypoint.py

ENTRYPOINT ["python", "/app/entrypoint.py"]
