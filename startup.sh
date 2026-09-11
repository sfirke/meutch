#!/bin/bash

# Exit on any error
set -e

echo "Starting deployment..."

# Run database migrations
echo "Running database migrations..."
flask db upgrade

echo "Database migrations completed successfully"

# Start the application
echo "Starting the application..."
# Two workers so one slow or stuck request does not take the whole site down.
# The timeout is a watchdog for a wedged worker, not a latency target: sync
# workers read the request body themselves, so a big photo upload over a slow
# phone connection counts against it and needs plenty of room.
exec gunicorn --workers 2 --timeout 120 "app:create_app()"
