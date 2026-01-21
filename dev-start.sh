#!/bin/bash
# Development startup script for Meutch

echo "🚀 Starting Meutch Development Environment"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run 'python -m venv venv' first."
    exit 1
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Simple CLI flags
# Usage: ./dev-start.sh [seed|--seed]
SEED=false
if [ "$1" = "seed" ] || [ "$1" = "--seed" ]; then
    SEED=true
fi

# Check if .env file exists (Flask will load it via python-dotenv)
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# Check if PostgreSQL container is running
if ! docker ps | grep -q "meutch-test-db"; then
    echo "🐳 Starting PostgreSQL container (docker-compose.test.yml)..."
    docker compose -f docker-compose.test.yml up -d
    
    # Wait for database to be ready
    echo "⏳ Waiting for database to be ready..."
    sleep 5
fi

echo "🔧 Environment configured from .env"

# Check for corrupted database state (alembic_version exists but tables don't)
echo "🔍 Checking database integrity..."
DB_TABLES=$(docker exec meutch-test-db psql -U test_user -d meutch_dev -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';" 2>/dev/null | tr -d ' ')
ALEMBIC_EXISTS=$(docker exec meutch-test-db psql -U test_user -d meutch_dev -t -c "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version');" 2>/dev/null | tr -d ' ')

# If alembic_version exists but we have fewer than expected tables (should be 15+), database is corrupted
if [ "$ALEMBIC_EXISTS" = "t" ] && [ "$DB_TABLES" -lt 10 ]; then
    echo "⚠️  Corrupted database detected (alembic_version exists but tables missing)"
    echo "🔧 Resetting database to fix migration state..."
    docker compose -f docker-compose.test.yml down -v
    echo "🐳 Starting fresh PostgreSQL container..."
    docker compose -f docker-compose.test.yml up -d
    echo "⏳ Waiting for database to be ready..."
    sleep 5
fi

# Run database migrations
echo "📊 Applying database migrations..."
flask db upgrade

if [ "$SEED" = true ]; then
    echo "🌱 Running development seed (idempotent)..."
    flask seed data --env development
fi

echo "✅ Environment ready!"
echo "🌐 Starting Flask development server..."
echo "📋 You can login with:"
echo "   Email: user1@example.com"
echo "   Password: password123"
echo ""

# Start Flask
flask run
