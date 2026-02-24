#!/bin/bash
# Development startup script for Meutch
set -euo pipefail

echo "🚀 Starting Meutch Development Environment"

wait_for_db() {
    echo "⏳ Waiting for database to be ready..."
    timeout=30
    while [ $timeout -gt 0 ]; do
        if docker exec meutch-test-db pg_isready -U test_user -d postgres > /dev/null 2>&1; then
            return 0
        fi
        sleep 1
        ((timeout--))
    done

    echo "❌ Timeout waiting for database to be ready"
    echo "💡 Troubleshooting:"
    echo "   - Ensure Docker daemon is running"
    echo "   - Check container logs: docker logs meutch-test-db"
    echo "   - If using docker compose and startup fails, validate .env syntax (no spaces around '=')"
    exit 1
}

table_exists() {
    local table_name="$1"
    docker exec meutch-test-db psql -U test_user -d meutch_dev -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='${table_name}'" 2>/dev/null | tr -d ' '
}

ensure_dev_schema() {
    local -a required_tables=("users" "category" "item")
    local -a missing_tables=()

    for table_name in "${required_tables[@]}"; do
        if [ "$(table_exists "$table_name")" != "1" ]; then
            missing_tables+=("$table_name")
        fi
    done

    if [ ${#missing_tables[@]} -eq 0 ]; then
        return 0
    fi

    echo "⚠️ Development schema is incomplete (missing: ${missing_tables[*]}). Attempting migration repair..."
    flask db stamp base
    flask db upgrade

    missing_tables=()
    for table_name in "${required_tables[@]}"; do
        if [ "$(table_exists "$table_name")" != "1" ]; then
            missing_tables+=("$table_name")
        fi
    done

    if [ ${#missing_tables[@]} -gt 0 ]; then
        echo "❌ Development schema is still incomplete after repair attempt (missing: ${missing_tables[*]})"
        echo "💡 Reset and rebuild the development database with:"
        echo "   docker exec meutch-test-db psql -U test_user -d postgres -c \"DROP DATABASE IF EXISTS meutch_dev; CREATE DATABASE meutch_dev;\""
        echo "   ./dev-start.sh seed"
        exit 1
    fi
}

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
if [ "${1:-}" = "seed" ] || [ "${1:-}" = "--seed" ]; then
    SEED=true
fi

# Check if .env file exists (Flask will load it via python-dotenv)
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# Validate docker compose configuration and .env syntax early
if ! docker compose -f docker-compose.test.yml config > /dev/null 2>&1; then
    echo "❌ Invalid docker compose configuration or .env syntax"
    echo "💡 Tip: ensure .env entries use KEY=value format (no spaces around '=')"
    docker compose -f docker-compose.test.yml config
    exit 1
fi

# Check if PostgreSQL container is running
if ! docker ps | grep -q "meutch-test-db"; then
    echo "🐳 Starting PostgreSQL container (docker-compose.test.yml)..."
    docker compose -f docker-compose.test.yml up -d
fi

wait_for_db

echo "🔧 Environment configured from .env"

echo "🔍 Ensuring development/test databases exist..."
for DB_NAME in meutch_dev meutch_test; do
    DB_EXISTS=$(docker exec meutch-test-db psql -U test_user -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" 2>/dev/null | tr -d ' ')
    if [ "$DB_EXISTS" != "1" ]; then
        echo "🆕 Creating database: ${DB_NAME}"
        docker exec meutch-test-db psql -U test_user -d postgres -c "CREATE DATABASE ${DB_NAME}" > /dev/null
    fi
done

# Run database migrations
echo "📊 Applying database migrations..."
flask db upgrade
ensure_dev_schema

if [ "$SEED" = true ]; then
    echo "🌱 Running development seed (idempotent)..."
    flask seed data --env development
fi

echo "✅ Environment ready!"
echo "🌐 Starting Flask development server..."
if [ "$SEED" = true ]; then
    echo "📋 You can login with:"
    echo "   Email: user1@example.com"
    echo "   Password: password123"
else
    echo "ℹ️ Running without seed data. Register a user at /auth/register or run ./dev-start.sh seed."
fi
echo ""

# Start Flask
flask run
