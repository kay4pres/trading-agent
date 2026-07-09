FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Berlin
ENV PYTHONPATH=/app

WORKDIR /app

# Install system deps + Python packages (pre-code)
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron tzdata unzip \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && pip install --no-cache-dir --break-system-packages \
        Flask flask-cors yfinance requests "python-telegram-bot>=20.7" croniter pandas numpy \
        tradingview-screener

# Pull latest code from GitHub
# CACHEBUST date must change to force a fresh download — update daily if needed
ARG CACHEBUST=20260709
ADD https://github.com/kay4pres/trading-agent/archive/refs/heads/main.zip?cachebust=${CACHEBUST} /app/repo.zip
RUN unzip /app/repo.zip \
    && mv /app/trading-agent-main/* /app/ \
    && rm -rf /app/repo.zip /app/trading-agent-main \
    && pip install --no-cache-dir --break-system-packages -r /app/requirements.txt \
    && chmod +x /app/entrypoint.py

ENTRYPOINT ["python", "/app/entrypoint.py"]
