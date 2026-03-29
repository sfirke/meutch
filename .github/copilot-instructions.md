# Meutch - Item Sharing & Lending Platform

Meutch is a nonprofit, open-source web application built with **Flask** (Python), **PostgreSQL**, and **Bootstrap** for the frontend. It enables community-based item sharing and lending. Users can list items for others to borrow, join lending circles, and communicate through the platform.

**Development Principles:**
- **Keep it simple and DRY:** Code should be easy to read and maintain, so that newer programmers can contribute confidently. Avoid unnecessary complexity and duplication.
- **Prioritize user privacy:** User data should be handled with care and only what is necessary should be stored or exposed.
- **Nonprofit & open-source:** All work should align with the mission to serve communities, not profit, and contributions are welcome from all.

**Tech Stack:**
- **Flask** (Python web framework)
- **PostgreSQL** (database; required for UUID columns)
- **Bootstrap** (CSS framework for UI)

**ALWAYS reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.**

## Working Effectively

### Initial Setup (First Time)
Only if the user is setting up for the first time, run these commands in exact order - NEVER CANCEL any of these operations:

```bash
# Install Python dependencies
pip install -r requirements.txt  # Takes 30 seconds

# Start test database
docker start meutch-test-db || docker compose -f docker-compose.test.yml up -d  # Takes 10 seconds
# NEVER CANCEL: Wait for database to fully start

# Set environment variables for testing
export TEST_DATABASE_URL=postgresql://test_user:test_password@localhost:5433/meutch_test
export SECRET_KEY=test-secret-key
export FLASK_APP=app.py
```

### Database Setup for Development
```bash
# For development with Docker PostgreSQL
export FLASK_ENV=development
export SECRET_KEY=dev-secret-key 
export DATABASE_URL=postgresql://test_user:test_password@localhost:5433/meutch_dev

# Run migrations
flask db upgrade  # Takes 1 second
```

### Running Tests

When you write a test, use factories from `tests/factories.py` to create test data.

**IMPORTANT:** Tests have been optimized for speed. The session-scoped app fixture means:
- Categories persist across tests - DO NOT hardcode category names in tests
- Use `CategoryFactory()` without the `name` parameter to get unique names
- Database schema is created once per test session, not per test

```bash
# CRITICAL: Always set TEST_DATABASE_URL before running tests
export TEST_DATABASE_URL=postgresql://test_user:test_password@localhost:5433/meutch_test

# Unit tests (fastest)
./run_tests.sh -u -c  # Takes ~5 seconds - NEVER CANCEL

# Integration tests  
./run_tests.sh -i     # Takes ~120 seconds - NEVER CANCEL

# Functional tests
./run_tests.sh -f     # Takes ~10 seconds - NEVER CANCEL

# All tests with coverage
./run_tests.sh -c     # Takes ~130 seconds - NEVER CANCEL
```

**TIMEOUT REQUIREMENTS:**
- Set timeouts to at least 120 seconds for all test commands
- **NEVER CANCEL** long-running operations - tests are optimized but still thorough


### Critical PostgreSQL Database Requirements
- Database connection on port 5433 (to avoid conflicts with system PostgreSQL)
- Test database automatically started by Docker with postgres:17-alpine image
- Always use TEST_DATABASE_URL for tests and DATABASE_URL for development

## Common Tasks & Commands

### Build and Test Pipeline
```bash
# Complete validation pipeline (run this before every commit)
export TEST_DATABASE_URL=postgresql://test_user:test_password@localhost:5433/meutch_test

# 1. Start database if needed
docker ps | grep meutch-test-db || docker compose -f docker-compose.test.yml up -d

# 2. Run full test suite - NEVER CANCEL - takes ~85 seconds  
./run_tests.sh -c

# 3. Start app and validate endpoints
export DATABASE_URL=postgresql://test_user:test_password@localhost:5433/meutch_dev
export SECRET_KEY=dev-secret-key
export FLASK_ENV=development
flask db upgrade
# Then start app and test endpoints as shown above
```

### Test Database Management
```bash
# Check database status
docker ps | grep meutch-test-db

# Start database
docker start meutch-test-db || docker compose -f docker-compose.test.yml up -d

# Stop database  
docker stop meutch-test-db

# Reset database (clean slate)
docker compose -f docker-compose.test.yml down -v
docker compose -f docker-compose.test.yml up -d
```

### File Storage
- Set `STORAGE_BACKEND` to `"local"` (dev, uses `app/static/uploads/`) or `"digitalocean"` (prod, requires `DO_SPACES_*` vars)
- Defaults to `"local"` in development; must be explicit in production/staging

## Development Workflow

### Making Changes
1. **Always start with setup commands** source the venv
2. **Run tests before making changes** to establish baseline
3. **Make small, focused changes**
4. **Run affected test suites immediately** after changes
5. **Document the PR's purpose** in CHANGELOG.md

### Common Change Scenarios
- **Model changes:** Run unit tests (`./run_tests.sh -u`), then integration tests (`./run_tests.sh -i`)
- **Route changes:** Run integration tests (`./run_tests.sh -i`)
- **Form changes:** Run unit tests for forms, then functional tests (`./run_tests.sh -f`)

## Troubleshooting

### Common Issues
- **Python not found:** Activate the venv at `./venv/bin/activate`
- **Database connection refused:** Start Docker database with `docker compose -f docker-compose.test.yml up -d`

### Production Deployment
- Uses `startup.sh` for basic production startup
- Uses `startup-staging.sh` for staging with data sync
- Requires PostgreSQL database with proper environment variables
- See `.github/workflows/` for CI/CD pipeline configuration

**Remember: Always validate your changes thoroughly by running the tests for any code that has been touched.**