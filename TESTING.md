# Testing Configuration and Strategy

This document outlines the testing strategy and configuration for the Meutch application.

## Test Structure

The test suite is organized into three main categories:

### 1. Unit Tests (`tests/unit/`)
- **Purpose**: Test individual components in isolation
- **Coverage**: Models, forms, utilities, and individual functions
- **Speed**: Fast execution (< 1 second per test)
- **Dependencies**: Minimal external dependencies, uses mocks where needed

### 2. Integration Tests (`tests/integration/`)
- **Purpose**: Test interaction between components
- **Coverage**: Route handlers, authentication flows, database operations
- **Speed**: Medium execution (1-5 seconds per test)
- **Dependencies**: Real database (SQLite in-memory for tests)

### 3. Functional Tests (`tests/functional/`)
- **Purpose**: End-to-end user workflow testing
- **Coverage**: Complete user journeys, cross-component functionality
- **Speed**: Slower execution (5-30 seconds per test)
- **Dependencies**: Full application stack

## Test Configuration

### Pytest Configuration (`pytest.ini`)
- Coverage target: 80% minimum
- Markers for organizing tests by type and feature
- HTML and XML coverage reports
- Verbose output with short tracebacks

### GitHub Actions CI/CD (`.github/workflows/ci.yml`)
- Runs on Python 3.9, 3.10, 3.11, 3.12
- PostgreSQL service for integration tests
- Security scanning with safety and bandit
- Coverage reporting to Codecov
- Automatic deployment on main branch

### Pre-commit Hooks (`.git/hooks/pre-commit`)
- Runs unit and integration tests before commit
- Prevents commits with failing tests
- Fast feedback loop for developers

## Running Tests

### Local Development

```bash
# Run all tests
./run_tests.sh

# Run specific test categories
./run_tests.sh --unit            # Unit tests only
./run_tests.sh --integration     # Integration tests only
./run_tests.sh --functional      # Functional tests only

# Run with coverage
./run_tests.sh --coverage

# Run with different verbosity
./run_tests.sh --verbose
./run_tests.sh --quiet

# Include slow tests
./run_tests.sh --slow
```

### Direct pytest commands

```bash
# All tests with coverage
pytest --cov=app --cov-report=html

# Specific test file
pytest tests/unit/test_models.py

# Specific test class
pytest tests/unit/test_models.py::TestUser

# Specific test method
pytest tests/unit/test_models.py::TestUser::test_user_creation

# Tests with specific marker
pytest -m "auth"
pytest -m "not slow"
```

## Test Data and Factories

### Factories (`tests/factories.py`)
- Uses Factory Boy for generating test data
- Provides realistic but controlled test data
- Reduces test setup boilerplate
- Ensures test independence

### Fixtures (`conftest.py`)
- Application and client fixtures for all tests
- Pre-configured test users (regular and admin)
- Helper functions for login/logout
- Database setup and teardown

## Coverage Requirements

### Minimum Coverage Targets
- **Overall**: 80%
- **Models**: 90%
- **Forms**: 85%
- **Routes**: 80%
- **Utilities**: 90%

### Coverage Exclusions
- Migration files
- Configuration files
- Test files themselves
- Development-only code

## Continuous Integration

### Pull Request Requirements
1. All tests must pass
2. Coverage threshold must be met
3. No new security vulnerabilities
4. Code formatting checks pass

### Deployment Requirements
1. Full test suite passes on main branch
2. Security scans complete successfully
3. Database migrations run successfully (dry run)
4. Performance benchmarks within acceptable range

## Test Data Management

### Database State
- Each test starts with a clean database
- Test data is created using factories
- No shared state between tests
- Automatic cleanup after each test

### File Uploads (Testing)
- Mock S3 operations in tests
- Use in-memory file storage
- Test file validation without actual uploads
- Verify upload error handling

### External Services
- Mock email sending in tests
- Mock external API calls
- Use test-specific configuration
- Isolated from production services

## Performance Testing

### Load Testing (Future Enhancement)
- Use locust or similar tool
- Test critical user journeys
- Monitor response times
- Database query optimization

### Benchmark Tests
- Track key metrics over time
- Alert on performance regressions
- Database query count monitoring
- Memory usage tracking

## Security Testing

### Automated Security Scanning
- Safety: Checks for known vulnerabilities in dependencies
- Bandit: Scans code for security issues
- OWASP compliance checking

### Manual Security Testing
- Authentication bypass attempts
- Authorization testing
- Input validation testing
- CSRF protection verification

## Maintenance

### Regular Tasks
1. Update test dependencies monthly
2. Review and update coverage targets quarterly
3. Clean up obsolete tests
4. Update test data as application evolves

### Monitoring
- Track test execution times
- Monitor flaky tests
- Analyze coverage trends
- Review test failure patterns

## Best Practices

### Writing Tests
1. Use descriptive test names
2. Follow AAA pattern (Arrange, Act, Assert)
3. One assertion per test when possible
4. Use factories instead of manual data creation
5. Mock external dependencies
6. Test both success and failure cases

### Test Organization
1. Group related tests in classes
2. Use appropriate test markers
3. Keep tests independent
4. Maintain test readability
5. Document complex test scenarios

### Debugging Tests
1. Use pytest's built-in debugging features
2. Run tests with -s flag to see print statements
3. Use --pdb flag to drop into debugger on failure
4. Check coverage reports for missed code paths
