FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Berlin
ENV PYTHONPATH=/app

WORKDIR /app

# Install system deps + Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron tzdata unzip \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && pip install --no-cache-dir --break-system-packages \
        Flask flask-cors yfinance requests "python-telegram-bot>=20.7" croniter pandas numpy \
        tradingview-screener alpaca-py

# ── Source of Truth ─────────────────────────────────────────────────────────
# The workflow clones from Gitea (http://10.8.0.10:3000/trading/trading-agent.git)
# into the build context at /build, then runs:
#   docker buildx build --file /build/docker/Dockerfile /build
# So COPY . /app here copies the Gitea-cloned repo (NOT GitHub).
COPY . /app
RUN pip install --no-cache-dir --break-system-packages -r /app/requirements.txt \
    && chmod +x /app/entrypoint.py

ENTRYPOINT ["python", "/app/entrypoint.py"]
