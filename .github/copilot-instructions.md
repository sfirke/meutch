
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
export TEST_DATABASE_URL=postgresql://test_user:test_password@localhost:5433/test_meutch
export SECRET_KEY=test-secret-key
export FLASK_APP=app.py
```

### Database Setup for Development
```bash
# For development with Docker PostgreSQL
export FLASK_ENV=development
export SECRET_KEY=dev-secret-key 
export DATABASE_URL=postgresql://test_user:test_password@localhost:5433/test_meutch

# Run migrations
flask db upgrade  # Takes 1 second
```

### Running Tests
```bash
# CRITICAL: Always set TEST_DATABASE_URL before running tests
export TEST_DATABASE_URL=postgresql://test_user:test_password@localhost:5433/test_meutch

# Unit tests (fastest)
./run_tests.sh -u -c  # Takes 18 seconds - NEVER CANCEL

# Integration tests  
./run_tests.sh -i     # Takes 30 seconds - NEVER CANCEL

# Functional tests
./run_tests.sh -f     # Takes 7 seconds - NEVER CANCEL

# All tests with coverage
./run_tests.sh -c     # Takes 56 seconds - NEVER CANCEL
```

**TIMEOUT REQUIREMENTS:**
- Set timeouts to at least 120 seconds for all test commands
- Set timeouts to at least 60 seconds for any build commands
- **NEVER CANCEL** long-running operations - tests may take up to 60 seconds

### Running the Web Application
```bash
# Start web server for testing changes
export FLASK_ENV=development
export SECRET_KEY=dev-secret-key
export DATABASE_URL=postgresql://test_user:test_password@localhost:5433/test_meutch
export FLASK_APP=app.py

# Ensure database is migrated first
flask db upgrade

# Start server
python -c "from app import create_app; app = create_app(); app.run(host='127.0.0.1', port=5000, debug=False)"
# Access at http://127.0.0.1:5000
```

## Validation Requirements

### MANDATORY Post-Change Validation
After making ANY code changes, ALWAYS run these validation steps:

1. **Test Suite Validation:**
   ```bash
   export TEST_DATABASE_URL=postgresql://test_user:test_password@localhost:5433/test_meutch
   ./run_tests.sh -c  # NEVER CANCEL - takes 56 seconds
   ```

2. **Web Application Testing:**
   ```bash
   # Start the app (commands above)
   # Test these endpoints return 200:
   curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/          # Homepage
   curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/about     # About page  
   curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/auth/login # Login page
   ```

3. **End-to-End User Scenarios:**
   Test these complete workflows through the web interface:
   - User registration and login flow
   - Create and list an item for lending
   - Browse available items
   - Send a message about an item
   - Create or join a lending circle

### Critical Database Requirements
- **PostgreSQL is REQUIRED** - SQLite will not work due to UUID column types
- Database connection on port 5433 (to avoid conflicts with system PostgreSQL)
- Test database automatically started by Docker with postgres:17-alpine image
- Always use TEST_DATABASE_URL for tests and DATABASE_URL for development

## Common Tasks & Commands

### Build and Test Pipeline
```bash
# Complete validation pipeline (run this before every commit)
export TEST_DATABASE_URL=postgresql://test_user:test_password@localhost:5433/test_meutch

# 1. Start database if needed
docker ps | grep meutch-test-db || docker compose -f docker-compose.test.yml up -d

# 2. Run full test suite - NEVER CANCEL - takes 56 seconds  
./run_tests.sh -c

# 3. Start app and validate endpoints
export DATABASE_URL=postgresql://test_user:test_password@localhost:5433/test_meutch
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

## Code Structure & Navigation

### Key Directories
- `app/` - Main Flask application
  - `app/main/` - Main blueprint (homepage, items, profiles)
  - `app/auth/` - Authentication routes
  - `app/circles/` - Lending circles functionality
  - `app/models.py` - Database models
  - `app/forms.py` - WTForms form definitions
  - `app/utils/storage.py` - File storage abstraction (local files or DO Spaces)
  - `app/static/uploads/` - Local file storage directory (git-ignored, except .gitkeep files)
- `tests/` - Test suite
  - `tests/unit/` - Unit tests (forms, models, storage)
  - `tests/integration/` - Integration tests (routes, auth)
  - `tests/functional/` - End-to-end workflow tests
- `migrations/` - Database migration files

### Important Files
- `app.py` - Application entry point
- `config.py` - Configuration classes for different environments
- `conftest.py` - Pytest configuration and fixtures
- `run_tests.sh` - Test runner script with multiple options
- `requirements.txt` - Python dependencies

### File Storage
The application supports two storage backends:
- **Local File Storage** (default for development): Files stored in `app/static/uploads/`
- **DigitalOcean Spaces** (production): S3-compatible object storage

Storage backend is automatically selected:
- Uses **DO Spaces** if all four credentials are configured (`DO_SPACES_KEY`, `DO_SPACES_SECRET`, `DO_SPACES_REGION`, `DO_SPACES_BUCKET`)
- Uses **local file storage** otherwise (safe default for development)

### Database Models
- `User` - User accounts with UUID primary keys
- `Item` - Items available for lending
- `Category` - Item categories (Tools, Electronics, Books, etc.)
- `Circle` - Lending circles/communities  
- `Message` - Direct messages between users
- `LoanRequest` - Formal loan requests for items

## Development Workflow

### Making Changes
1. **Always start with setup commands** (database + environment variables)
2. **Run tests before making changes** to establish baseline
3. **Make small, focused changes**
4. **Run affected test suites immediately** after changes
5. **Run full test suite** before considering work complete
6. **Test web application manually** for user-facing changes
7. **Never skip validation steps** - they catch issues early

### Common Change Scenarios
- **Model changes:** Run unit tests (`./run_tests.sh -u`), then integration tests (`./run_tests.sh -i`)
- **Route changes:** Run integration tests (`./run_tests.sh -i`), then test web app manually
- **Form changes:** Run unit tests for forms, then functional tests (`./run_tests.sh -f`)
- **Any user-facing changes:** Always test through web interface after automated tests pass

### Configuration Environments
- `development` - Local development with PostgreSQL
- `testing` - Test environment (used by pytest)  
- `staging` - Staging environment with production data sync
- `production` - Production deployment

## Troubleshooting

### Common Issues
- **Python not found:** Activate the venv at `./venv/bin/activate`
- **Database connection refused:** Start Docker database with `docker compose -f docker-compose.test.yml up -d`

### Production Deployment
- Uses `startup.sh` for basic production startup
- Uses `startup-staging.sh` for staging with data sync
- Requires PostgreSQL database with proper environment variables
- See `.github/workflows/` for CI/CD pipeline configuration

**Remember: Always validate your changes thoroughly using both automated tests and manual web application testing.**