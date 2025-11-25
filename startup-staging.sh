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

# Sync production data to staging if both database URLs are available
if [ -n "$PROD_DATABASE_URL" ] && [ -n "$STAGING_DATABASE_URL" ]; then
    echo "📊 Starting production data sync..."
    echo "💡 This creates a clean copy of production (schema + data + migration state)"
    python sync_staging_db.py
    echo "✅ Production data sync completed"
    
    # Run any NEW migrations that exist in staging code but not in production
    echo "🔄 Running new migrations (if any)..."
    flask db upgrade
    echo "✅ Migrations completed"
else
    echo "⚠️  Skipping production sync (environment variables not set)"
    echo "🔄 Running database migrations for empty database..."
    flask db upgrade
    echo "✅ Migrations completed"
fi

echo "✅ Staging startup completed successfully!"
echo "🌐 Application ready to serve requests"

# Start the application with gunicorn  
echo "🚀 Starting gunicorn server..."
cd /workspace
export PYTHONPATH="/workspace:$PYTHONPATH"
exec gunicorn --bind 0.0.0.0:8080 --workers 2 --timeout 120 --access-logfile - --chdir /workspace wsgi:application
