-- Initialize the test database
-- This script runs when the Docker container starts

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create additional test databases if needed
-- CREATE DATABASE test_meutch_integration;
-- CREATE DATABASE test_meutch_functional;

-- Set up any additional test-specific configuration
-- ALTER DATABASE test_meutch SET timezone = 'UTC';
