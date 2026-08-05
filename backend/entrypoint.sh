#!/bin/bash
set -e
echo "⏳ Waiting for PostgreSQL..."
until pg_isready -h "${PGHOST:-postgres}" -p "${PGPORT:-5432}" -U "${PGUSER:-lexiact}" -q 2>/dev/null; do
    echo "   not ready, retrying..."
    sleep 1
done
echo "✅ PostgreSQL ready"
echo "🔄 Running migrations..."
alembic upgrade head
echo "✅ Migrations done"
echo "🚀 Starting LexiAct..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
