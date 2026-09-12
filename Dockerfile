FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# curl is used by the compose healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install the fully resolved set, not the direct-dependency list, so the image
# is reproducible: the same commit builds the same stack on any day.
COPY requirements.txt requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt

COPY . .

# settings.py reads DJANGO_SECRET_KEY and DATABASE_URL at import time and the
# real values are not present at build time (and must not be). These throwaway
# values only let the settings module import; collectstatic opens no socket.
RUN DJANGO_SECRET_KEY=build-time-only \
    DATABASE_URL=postgres://u:p@localhost:5432/db \
    python manage.py collectstatic --noinput

RUN adduser --disabled-password --gecos "" appuser \
    && chmod +x /app/entrypoint.sh
USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info"]
