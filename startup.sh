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
exec gunicorn "app:create_app()"
