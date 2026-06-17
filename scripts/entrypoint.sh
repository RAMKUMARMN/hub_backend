#!/bin/sh

# Exit on error
set -e

echo "Waiting for database to be ready..."
python3 -c "
import sys
import time
import socket
import urllib.parse
import os

db_url = os.environ.get('DATABASE_URL', '')
if 'postgresql' in db_url:
    try:
        # Extract hostname and port
        # Handle asyncpg scheme (postgresql+asyncpg://...)
        clean_url = db_url.replace('+asyncpg', '')
        u = urllib.parse.urlparse(clean_url)
        host = u.hostname
        port = u.port or 5432
        
        print(f'Checking connection to database at {host}:{port}...')
        for i in range(30):
            try:
                with socket.create_connection((host, port), timeout=2):
                    print('Database is ready!')
                    sys.exit(0)
            except OSError:
                print(f'Attempt {i+1}/30: Database not ready yet, retrying in 2 seconds...')
                time.sleep(2)
        print('Timeout: Database did not become ready in time.')
        sys.exit(1)
    except Exception as e:
        print(f'Could not parse or check database: {e}')
else:
    print('SQLite or other non-Postgres DB detected, skipping connection check.')
"

# Run alembic migrations
echo "Running alembic migrations..."
alembic upgrade head

# Start FastAPI application
echo "Starting FastAPI server..."
# Check if reload is enabled (useful for local dev)
if [ "$DEBUG" = "True" ] || [ "$DEBUG" = "true" ]; then
    echo "Running with Uvicorn auto-reload..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
else
    echo "Running in production mode..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
