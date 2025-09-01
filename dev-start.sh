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

# Check if PostgreSQL container is running
if ! docker ps | grep -q "meutch.*db"; then
    echo "🐳 Starting PostgreSQL container..."
    docker-compose up -d
    
    # Wait for database to be ready
    echo "⏳ Waiting for database to be ready..."
    sleep 5
fi

# Check if development database exists
if ! docker exec meutch-test-db psql -U test_user -lqt | cut -d \| -f 1 | grep -qw meutch_dev; then
    echo "🗄️  Creating development database..."
    docker exec meutch-test-db createdb -U test_user meutch_dev
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
