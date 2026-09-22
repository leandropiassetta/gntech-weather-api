#!/bin/sh

set -eu

attempt=1
max_attempts="${DB_WAIT_MAX_ATTEMPTS:-30}"
wait_interval="${DB_WAIT_INTERVAL_SECONDS:-1}"

echo "Waiting for PostgreSQL..."

until python -c '
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.db import connections

connections["default"].ensure_connection()
' >/dev/null 2>&1; do
    if [ "$attempt" -ge "$max_attempts" ]; then
        echo "PostgreSQL is unavailable after ${max_attempts} attempts." >&2
        exit 1
    fi

    echo "PostgreSQL is unavailable - attempt ${attempt}/${max_attempts}."
    attempt=$((attempt + 1))
    sleep "$wait_interval"
done

echo "PostgreSQL is available."
echo "Applying database migrations..."
python manage.py migrate --noinput

exec "$@"

