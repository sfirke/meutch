#!/bin/bash
# Staging startup script for DigitalOcean App Platform

set -e  # Exit on any error

echo "🚀 Starting Meutch Staging Application..."

# Set staging environment
export FLASK_ENV=staging

echo "Environment: staging"
echo "Database: ${DATABASE_URL:0:20}..."

# Check for SECRET_KEY with alternative method
# Ensure we have required environment variables
if [ -z "$SECRET_KEY" ]; then
    echo "❌ ERROR: SECRET_KEY environment variable is required"
    exit 1
fi

if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL environment variable is required"
    exit 1
fi

# Run database migrations
echo "🔄 Running database migrations..."
flask db upgrade

echo "✅ Database migrations completed successfully"

# Sync production data to staging if both database URLs are available
echo "🔍 Checking environment variables for sync:"
echo "   PROD_DATABASE_URL: ${PROD_DATABASE_URL:+SET}${PROD_DATABASE_URL:-NOT_SET}"
echo "   STAGING_DATABASE_URL: ${STAGING_DATABASE_URL:+SET}${STAGING_DATABASE_URL:-NOT_SET}"

if [ -n "$PROD_DATABASE_URL" ] && [ -n "$STAGING_DATABASE_URL" ]; then
    echo "📊 Starting production data sync in background..."
    nohup python sync_staging_db.py > /tmp/sync.log 2>&1 &
    SYNC_PID=$!
    echo "💡 Sync running in background (PID: $SYNC_PID) - check /tmp/sync.log for status"
    echo "   App will start immediately and sync will complete shortly"
else
    echo "⚠️  Required environment variables not set, skipping production data sync"
    echo "   Staging will use empty database"
fi

echo "✅ Staging startup completed successfully!"
echo "🌐 Application ready to serve requests"

# Start the application with gunicorn  
echo "🚀 Starting gunicorn server..."
cd /workspace
export PYTHONPATH="/workspace:$PYTHONPATH"
exec gunicorn --bind 0.0.0.0:8080 --workers 2 --timeout 120 --access-logfile - --chdir /workspace wsgi:application
