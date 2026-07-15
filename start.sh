#!/bin/bash

set -e

MAX_RETRIES=10
RETRY_COUNT=0
RETRY_DELAY=5

echo "Waiting for database connection..."

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if python -c "from database.database import engine; engine.connect(); print('Database connection successful')" 2>/dev/null; then
        echo "Database is ready!"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Database not ready. Retry $RETRY_COUNT/$MAX_RETRIES (waiting ${RETRY_DELAY}s)..."
    sleep $RETRY_DELAY
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "Failed to connect to database after $MAX_RETRIES attempts"
    exit 1
fi

echo "Applying database migrations..."

if ! alembic upgrade head; then
    echo "Migration failed"
    exit 1
fi

echo "Migrations completed successfully"
echo "Starting application server..."

exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} --log-level info
