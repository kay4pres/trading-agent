FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Berlin
ENV PYTHONPATH=/app

WORKDIR /app

# Install system deps + Python packages + git (for cloning)
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron tzdata unzip git \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && pip install --no-cache-dir --break-system-packages \
        Flask flask-cors yfinance requests "python-telegram-bot>=20.7" croniter pandas numpy \
        tradingview-screener

# Build argument: GIT_REF (defaults to main)
# GITEA_TOKEN build arg: bearer token for authenticated clone from Gitea
ARG GIT_REF=main
ARG GITEA_TOKEN=
ENV GITEA_TOKEN=${GITEA_TOKEN}
RUN git clone --depth=1 --branch=${GIT_REF} \
    http://kay:${GITEA_TOKEN}@10.8.0.10:3000/kay/trading-agent.git /app \
    && rm -rf /app/.git \
    && pip install --no-cache-dir --break-system-packages -r /app/requirements.txt \
    && chmod +x /app/entrypoint.py

ENTRYPOINT ["python", "/app/entrypoint.py"]
