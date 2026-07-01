FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Berlin
ENV PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    cron tzdata unzip \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && pip install --no-cache-dir --break-system-packages \
        Flask flask-cors yfinance requests "python-telegram-bot>=20.7" croniter pandas numpy

# Build argument: GIT_REF (defaults to main)
ARG GIT_REF=main
ADD https://github.com/kay4pres/trading-agent/archive/refs/heads/${GIT_REF}.zip /app/repo.zip
RUN unzip /app/repo.zip \
    && mv /app/trading-agent-${GIT_REF}/* /app/ \
    && rm -rf /app/repo.zip /app/trading-agent-${GIT_REF}

ENTRYPOINT ["python", "/app/entrypoint.py"]
