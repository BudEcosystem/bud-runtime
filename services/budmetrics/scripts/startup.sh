#!/bin/bash
set -e

echo "Starting bud-serve-metrics..."

# Run ClickHouse migrations
echo "Running ClickHouse migrations..."
python scripts/migrate_clickhouse.py

# Check if migration was successful
if [ $? -eq 0 ]; then
    echo "Migrations completed successfully"
else
    echo "Migration failed, exiting..."
    exit 1
fi

# Start the application
echo "Starting uvicorn server..."
exec uvicorn budmetrics.main:app --host 0.0.0.0 --port $APP_PORT --reload
