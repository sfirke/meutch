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

echo "💡 Staging uses production data copy for authentic testing"
echo "   To sync latest data: python sync_staging_db.py"

echo "✅ Staging startup completed successfully!"
echo "🌐 Application ready to serve requests"

# Test that the Flask app can be imported
echo "🧪 Testing Flask app import..."
python3 -c "
import sys
sys.path.append('.')
try:
    from app import create_app
    app = create_app()
    print('✅ Flask app created successfully')
    print(f'App config: {app.config.get(\"ENV\", \"unknown\")}')
except Exception as e:
    print(f'❌ Error creating Flask app: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

# Start the application with gunicorn  
echo "🚀 Starting gunicorn server..."
exec gunicorn --bind 0.0.0.0:8080 --workers 2 --timeout 120 --access-logfile - app:app
