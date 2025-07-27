#!/bin/bash
# Staging startup script for DigitalOcean App Platform

set -e  # Exit on any error

echo "🚀 Starting Meutch Staging Application..."

# Set staging environment
export FLASK_ENV=staging

echo "Environment: staging"
echo "Database: ${DATABASE_URL:0:20}..."

# Check for SECRET_KEY with alternative method
# Check for SECRET_KEY with more detailed debugging
echo "🔍 Detailed SECRET_KEY debugging:"
echo "  - Raw SECRET_KEY: '${SECRET_KEY}'"
echo "  - SECRET_KEY length: ${#SECRET_KEY}"
echo "  - SECRET_KEY with default: '${SECRET_KEY:-UNSET}'"
echo "  - All environment variables:"
env | sort

# For now, let's proceed even if SECRET_KEY seems empty, as Flask will catch it
if [ -z "$SECRET_KEY" ]; then
    echo "⚠️  WARNING: SECRET_KEY appears empty, but proceeding..."
    echo "   Flask will error if SECRET_KEY is truly missing"
else
    echo "✅ SECRET_KEY is set (length: ${#SECRET_KEY})"
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
