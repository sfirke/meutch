# Test Database Setup Guide

This guide explains how to set up and use the Docker PostgreSQL database for testing the Meutch application.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.9+ with pip
- Git

## Quick Start

1. **Start the test database:**
   ```bash
   ./test-db.sh start
   ```

2. **Run database migrations:**
   ```bash
   ./test-db.sh migrate
   ```

3. **Run the test suite:**
   ```bash
   ./run_tests.sh
   ```

## Detailed Setup

### 1. Test Database Management

The `test-db.sh` script provides comprehensive database management:

```bash
# Start the test database
./test-db.sh start

# Stop the test database
./test-db.sh stop

# Restart the test database
./test-db.sh restart

# Reset database (clean slate - removes all data)
./test-db.sh reset

# Check database status
./test-db.sh status

# Connect to database with psql
./test-db.sh connect

# Run database migrations
./test-db.sh migrate

# View database logs
./test-db.sh logs
```

### 2. Database Configuration

The test database runs on Docker with the following configuration:

- **Host:** localhost
- **Port:** 5433 (to avoid conflicts with local PostgreSQL)
- **Database:** test_meutch
- **Username:** test_user
- **Password:** test_password
- **Connection URL:** `postgresql://test_user:test_password@localhost:5433/test_meutch`

### 3. Local PostgreSQL Conflicts

If you have local PostgreSQL running on port 5432, you have two options:

**Option 1: Stop local PostgreSQL (recommended for testing)**
```bash
sudo systemctl stop postgresql
sudo systemctl disable postgresql  # To prevent auto-start
```

**Option 2: Keep both running**
The Docker database uses port 5433, so both can run simultaneously.

### 4. Running Tests

The test runner (`run_tests.sh`) automatically:
- Checks if the test database is running
- Starts it if needed
- Sets the correct environment variables
- Runs the test suite

```bash
# Run all tests
./run_tests.sh

# Run specific test types
./run_tests.sh --unit
./run_tests.sh --integration
./run_tests.sh --functional

# Run with coverage
./run_tests.sh --coverage
```

### 5. Manual Test Execution

You can also run tests manually with pytest:

```bash
# Set environment variables
export TEST_DATABASE_URL="postgresql://test_user:test_password@localhost:5433/test_meutch"
export FLASK_ENV=testing

# Run tests
pytest tests/
```

## Docker Compose Configuration

The test database is defined in `docker-compose.test.yml`:

```yaml
services:
  test-postgres:
    image: postgres:17-alpine
    environment:
      POSTGRES_DB: test_meutch
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
    ports:
      - "5433:5432"
```

You can also manage it directly with Docker Compose:
```bash
# Start the database
docker compose -f docker-compose.test.yml up -d

# Stop the database
docker compose -f docker-compose.test.yml down

# View logs
docker compose -f docker-compose.test.yml logs test-postgres
```

## Database Initialization

The database is initialized with:
- UUID extension enabled (`uuid-ossp`)
- Clean database schema from Flask-Migrate migrations
- Test-specific configuration

## Troubleshooting

### Database Connection Issues

1. **Check if Docker is running:**
   ```bash
   docker info
   ```

2. **Check database status:**
   ```bash
   ./test-db.sh status
   ```

3. **Check database logs:**
   ```bash
   ./test-db.sh logs
   ```

4. **Reset database:**
   ```bash
   ./test-db.sh reset
   ```

### Port Conflicts

If you get port conflict errors:

1. **Check what's using port 5433:**
   ```bash
   lsof -i :5433
   ```

2. **Stop local PostgreSQL:**
   ```bash
   sudo systemctl stop postgresql
   ```

### Migration Issues

1. **Reset and remigrate:**
   ```bash
   ./test-db.sh reset
   ./test-db.sh migrate
   ```

2. **Check migration status:**
   ```bash
   export DATABASE_URL="postgresql://test_user:test_password@localhost:5433/test_meutch"
   flask db current
   ```

### Test Failures

1. **Check test database is running:**
   ```bash
   ./test-db.sh status
   ```

2. **Run tests with verbose output:**
   ```bash
   ./run_tests.sh --verbose
   ```

3. **Run specific failing test:**
   ```bash
   pytest tests/path/to/test.py::TestClass::test_method -v
   ```

## CI/CD Integration

The GitHub Actions workflow automatically:
- Starts a PostgreSQL service container
- Uses the same database configuration
- Runs the full test suite
- Reports coverage

## Best Practices

1. **Always reset database before important test runs:**
   ```bash
   ./test-db.sh reset
   ```

2. **Keep test data isolated:**
   - Each test should clean up after itself
   - Use database transactions for test isolation
   - Use factories for test data creation

3. **Monitor test performance:**
   - Use `./run_tests.sh --verbose` to see timing
   - Optimize slow tests
   - Use appropriate test markers

4. **Regular maintenance:**
   - Update Docker images periodically
   - Clean up unused Docker volumes
   - Review and update test data

## Commands Reference

| Command | Purpose |
|---------|---------|
| `./test-db.sh start` | Start test database |
| `./test-db.sh stop` | Stop test database |
| `./test-db.sh reset` | Clean database reset |
| `./test-db.sh migrate` | Run migrations |
| `./test-db.sh connect` | Connect with psql |
| `./run_tests.sh` | Run all tests |
| `./run_tests.sh --coverage` | Run with coverage |
| `./run_tests.sh --unit` | Run unit tests only |

## Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `TEST_DATABASE_URL` | Test database connection | `postgresql://test_user:test_password@localhost:5433/test_meutch` |
| `FLASK_ENV` | Flask environment | `testing` |
| `PYTHONPATH` | Python module path | Current directory |
