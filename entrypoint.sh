#!/bin/sh
# Runs migrations before handing off to the real command.
#
# Only the web container should migrate. The celery worker shares this image
# but must not race the web container for the migration lock, so it is started
# with RUN_MIGRATIONS unset.
set -e

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    echo "==> Applying database migrations"
    python manage.py migrate --noinput
fi

exec "$@"
