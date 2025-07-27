#!/bin/bash
# Staging startup script for DigitalOcean App Platform

set -e  # Exit on any error

echo "🚀 Starting Meutch Staging Application..."

# Set staging environment
export FLASK_ENV=staging

echo "Environment: staging"
echo "Database: ${DATABASE_URL:0:20}..."

# Check for SECRET_KEY and provide helpful debugging info
if [ -z "$SECRET_KEY" ]; then
    echo "❌ ERROR: SECRET_KEY environment variable is required"
    echo "🔍 Debug info:"
    echo "  - Available environment variables:"
    env | grep -E "(SECRET|FLASK|DATABASE)" | sed 's/=.*/=***/' || echo "  - No matching environment variables found"
    echo "  - Please ensure SECRET_KEY is set in DigitalOcean App Platform"
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

echo "💡 Staging uses production data copy for authentic testing"
echo "   To sync latest data: python sync_staging_db.py"

echo "✅ Staging startup completed successfully!"
echo "🌐 Application ready to serve requests"

# Start the application with gunicorn  
exec gunicorn --bind 0.0.0.0:8080 --workers 2 --timeout 120 app:app
