#!/bin/bash

# Test runner script for Meutch application
# This script runs the complete test suite with different options

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    printf "${1}${2}${NC}\n"
}

# Function to print usage
usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -u, --unit         Run only unit tests"
    echo "  -i, --integration  Run only integration tests"
    echo "  -f, --functional   Run only functional tests"
    echo "  -c, --coverage     Run tests with coverage report"
    echo "  -q, --quiet        Run tests in quiet mode"
    echo "  -v, --verbose      Run tests in verbose mode"
    echo "  -s, --slow         Include slow tests"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                 # Run all tests"
    echo "  $0 -u -c          # Run unit tests with coverage"
    echo "  $0 -f -v          # Run functional tests verbosely"
}

# Default options
RUN_UNIT=false
RUN_INTEGRATION=false
RUN_FUNCTIONAL=false
RUN_ALL=true
COVERAGE=false
QUIET=false
VERBOSE=false
INCLUDE_SLOW=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--unit)
            RUN_UNIT=true
            RUN_ALL=false
            shift
            ;;
        -i|--integration)
            RUN_INTEGRATION=true
            RUN_ALL=false
            shift
            ;;
        -f|--functional)
            RUN_FUNCTIONAL=true
            RUN_ALL=false
            shift
            ;;
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -q|--quiet)
            QUIET=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -s|--slow)
            INCLUDE_SLOW=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option $1"
            usage
            exit 1
            ;;
    esac
done

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    print_color $RED "pytest is not installed. Please install it with: pip install pytest"
    exit 1
fi

# Set up environment
export FLASK_ENV=testing
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export TEST_DATABASE_URL="postgresql://test_user:test_password@localhost:5433/meutch_dev"

print_color $BLUE "🧪 Running Meutch Test Suite"
print_color $BLUE "================================"

# Check if test database is running and healthy
check_test_db() {
    # Check if container exists and is running
    if ! docker ps --filter "name=meutch-test-db" --format "{{.Names}}" | grep -q "meutch-test-db"; then
        return 1
    fi
    
    # Check if database is actually ready to accept connections
    if ! docker compose -f docker-compose.test.yml exec -T test-postgres pg_isready -U test_user -d meutch_dev > /dev/null 2>&1; then
        return 1
    fi
    
    return 0
}

if ! check_test_db; then
    print_color $YELLOW "⚠️  Test database is not running or not ready. Starting it now..."
    
    # Stop any potentially problematic containers first
    docker compose -f docker-compose.test.yml down > /dev/null 2>&1 || true
    
    # Start the test database
    ./test-db.sh start
    if [ $? -ne 0 ]; then
        print_color $RED "❌ Failed to start test database. Please run './test-db.sh start' manually."
        exit 1
    fi
    
    # Double-check that it's ready
    if ! check_test_db; then
        print_color $RED "❌ Test database started but is not ready. Please check './test-db.sh status'."
        exit 1
    fi
    
    print_color $GREEN "✅ Test database is now ready!"
fi

# Build pytest command
PYTEST_CMD="pytest"

# Add verbosity options
if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
elif [ "$QUIET" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -q"
fi

# Add coverage options
if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=app --cov-report=html:htmlcov --cov-report=term-missing --cov-report=xml"
fi

# Add slow test marker
if [ "$INCLUDE_SLOW" = false ]; then
    PYTEST_CMD="$PYTEST_CMD -m \"not slow\""
fi

# Determine which tests to run
if [ "$RUN_ALL" = true ]; then
    print_color $YELLOW "Running all tests..."
    TEST_PATH="tests/"
elif [ "$RUN_UNIT" = true ]; then
    print_color $YELLOW "Running unit tests..."
    TEST_PATH="tests/unit/"
elif [ "$RUN_INTEGRATION" = true ]; then
    print_color $YELLOW "Running integration tests..."
    TEST_PATH="tests/integration/"
elif [ "$RUN_FUNCTIONAL" = true ]; then
    print_color $YELLOW "Running functional tests..."
    TEST_PATH="tests/functional/"
else
    # Multiple test types selected
    TEST_PATH=""
    if [ "$RUN_UNIT" = true ]; then
        TEST_PATH="$TEST_PATH tests/unit/"
    fi
    if [ "$RUN_INTEGRATION" = true ]; then
        TEST_PATH="$TEST_PATH tests/integration/"
    fi
    if [ "$RUN_FUNCTIONAL" = true ]; then
        TEST_PATH="$TEST_PATH tests/functional/"
    fi
fi

# Run the tests
print_color $BLUE "Executing: $PYTEST_CMD $TEST_PATH"
echo ""

if eval "$PYTEST_CMD $TEST_PATH"; then
    print_color $GREEN "✅ All tests passed!"
    
    if [ "$COVERAGE" = true ]; then
        print_color $BLUE "📊 Coverage report generated:"
        print_color $BLUE "  - HTML: htmlcov/index.html"
        print_color $BLUE "  - XML: coverage.xml"
    fi
else
    print_color $RED "❌ Some tests failed!"
    exit 1
fi

print_color $BLUE ""
print_color $BLUE "Test run completed successfully! 🎉"
