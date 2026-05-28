#!/usr/bin/env bash
set -e

echo "Waiting for Postgres at ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."
until python -c "import socket,os; s=socket.socket(); s.settimeout(2); s.connect((os.environ.get('POSTGRES_HOST','db'), int(os.environ.get('POSTGRES_PORT','5432'))))" 2>/dev/null; do
  sleep 1
done
echo "Postgres is up."

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "Applying migrations and seeding..."
  # Do NOT run makemigrations here: migrations are committed in VCS and
  # generating them at boot would (a) write root-owned files into the host
  # volume in dev and (b) mask "missing migration" errors in prod.
  python manage.py migrate --noinput
  python manage.py seed_questions
fi

exec "$@"
