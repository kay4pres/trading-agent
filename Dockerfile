FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Berlin
ENV PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    cron tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && pip install --no-cache-dir --break-system-packages \
        Flask flask-cors yfinance requests "python-telegram-bot>=20.7" croniter pandas numpy

# Download repo from GitHub (public, no auth needed)
ADD https://github.com/kay4pres/trading-agent/archive/refs/heads/main.zip /app/repo.zip
RUN unzip /app/repo.zip \
    && mv /app/trading-agent-main/* /app/ \
    && rm -rf /app/repo.zip /app/trading-agent-main \
    && chmod +x /app/entrypoint.py

ENTRYPOINT ["python", "/app/entrypoint.py"]
