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
        tradingview-screener

# Build argument: GIT_REF (defaults to main)
# CACHEBUST date changes daily — forces fresh GitHub download every 24h
ARG GIT_REF=main
ARG CACHEBUST=20260707
ADD https://github.com/kay4pres/trading-agent/archive/refs/heads/${GIT_REF}.zip /app/repo.zip
RUN unzip /app/repo.zip \
    && mv /app/trading-agent-${GIT_REF}/* /app/ \
    && rm -rf /app/repo.zip /app/trading-agent-${GIT_REF} \
    && pip install --no-cache-dir --break-system-packages -r /app/requirements.txt \
    && chmod +x /app/entrypoint.py

ENTRYPOINT ["python", "/app/entrypoint.py"]
