#!/usr/bin/env bash
set -e

echo "Waiting for Postgres at ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."
until python -c "import socket,os; s=socket.socket(); s.settimeout(2); s.connect((os.environ.get('POSTGRES_HOST','db'), int(os.environ.get('POSTGRES_PORT','5432'))))" 2>/dev/null; do
  sleep 1
done
echo "Postgres is up."

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "Applying migrations and seeding..."
  python manage.py makemigrations accounts bank papers --noinput
  python manage.py migrate --noinput
  python manage.py seed_questions
fi

exec "$@"
