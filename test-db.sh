#!/bin/bash

# Test Database Management Script
# Manages the Docker PostgreSQL database for testing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_color() {
    printf "${1}${2}${NC}\n"
}

# Docker compose file for tests
DOCKER_COMPOSE_FILE="docker-compose.test.yml"
CONTAINER_NAME="meutch-test-db"
TEST_DB_NAME="meutch_test"

ensure_test_db_exists() {
    DB_EXISTS=$(docker exec $CONTAINER_NAME psql -U test_user -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${TEST_DB_NAME}'" 2>/dev/null | tr -d ' ')
    if [ "$DB_EXISTS" != "1" ]; then
        print_color $BLUE "🆕 Creating test database: ${TEST_DB_NAME}"
        docker exec $CONTAINER_NAME psql -U test_user -d postgres -c "CREATE DATABASE ${TEST_DB_NAME}" > /dev/null
    fi
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_color $RED "❌ Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Function to start the test database
start_db() {
    print_color $BLUE "🚀 Starting test database..."
    
    check_docker
    
    # Start the Docker database
    docker compose -f $DOCKER_COMPOSE_FILE up -d
    
    # Wait for database to be ready
    print_color $BLUE "⏳ Waiting for database to be ready..."
    timeout=30
    while [ $timeout -gt 0 ]; do
        if docker compose -f $DOCKER_COMPOSE_FILE exec -T test-postgres pg_isready -U test_user -d postgres > /dev/null 2>&1; then
            print_color $GREEN "✅ Test database is ready!"
            break
        fi
        sleep 1
        ((timeout--))
    done
    
    if [ $timeout -eq 0 ]; then
        print_color $RED "❌ Timeout waiting for database to be ready"
        exit 1
    fi

    ensure_test_db_exists
    
    print_color $GREEN "🎉 Test database started successfully!"
    print_color $BLUE "Database URL (tests): postgresql://test_user:test_password@localhost:5433/${TEST_DB_NAME}"
    print_color $BLUE "Database URL (dev): postgresql://test_user:test_password@localhost:5433/meutch_dev"
}

# Function to stop the test database
stop_db() {
    print_color $BLUE "🛑 Stopping test database..."
    docker compose -f $DOCKER_COMPOSE_FILE down
    print_color $GREEN "✅ Test database stopped!"
}

# Function to restart the test database
restart_db() {
    print_color $BLUE "🔄 Restarting test database..."
    stop_db
    start_db
}

# Function to reset the test database (clean slate)
reset_db() {
    print_color $BLUE "🗑️  Resetting test database..."
    docker compose -f $DOCKER_COMPOSE_FILE down -v
    start_db
    print_color $GREEN "✅ Test database reset complete!"
}

# Function to show database status
status_db() {
    print_color $BLUE "📊 Test database status:"
    if docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -q $CONTAINER_NAME; then
        docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        print_color $GREEN "✅ Test database is running"
    else
        print_color $YELLOW "⚠️  Test database is not running"
    fi
}

# Function to connect to database with psql
connect_db() {
    print_color $BLUE "🔗 Connecting to test database..."
    docker compose -f $DOCKER_COMPOSE_FILE exec test-postgres psql -U test_user -d $TEST_DB_NAME
}

# Function to run database migrations
migrate_db() {
    print_color $BLUE "🔄 Running database migrations..."
    
    # Set the test database URL
    export FLASK_APP=app.py
    export DATABASE_URL="postgresql://test_user:test_password@localhost:5433/$TEST_DB_NAME"
    
    # Run migrations
    flask db upgrade
    
    print_color $GREEN "✅ Database migrations completed!"
}

# Function to show logs
logs_db() {
    print_color $BLUE "📝 Test database logs:"
    docker compose -f $DOCKER_COMPOSE_FILE logs -f test-postgres
}

# Function to show usage
usage() {
    echo "Usage: $0 {start|stop|restart|reset|status|connect|migrate|logs|help}"
    echo ""
    echo "Commands:"
    echo "  start     Start the test database"
    echo "  stop      Stop the test database"
    echo "  restart   Restart the test database"
    echo "  reset     Reset the test database (removes all data)"
    echo "  status    Show database status"
    echo "  connect   Connect to database with psql"
    echo "  migrate   Run database migrations"
    echo "  logs      Show database logs"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start          # Start the test database"
    echo "  $0 reset          # Reset database to clean state"
    echo "  $0 migrate        # Run database migrations"
    echo "  $0 connect        # Connect with psql"
}

# Main command handling
case "$1" in
    start)
        start_db
        ;;
    stop)
        stop_db
        ;;
    restart)
        restart_db
        ;;
    reset)
        reset_db
        ;;
    status)
        status_db
        ;;
    connect)
        connect_db
        ;;
    migrate)
        migrate_db
        ;;
    logs)
        logs_db
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        print_color $RED "❌ Unknown command: $1"
        echo ""
        usage
        exit 1
        ;;
esac
