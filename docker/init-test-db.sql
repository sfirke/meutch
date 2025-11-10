-- Initialize the test database
-- This script runs when the Docker container starts

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create additional test databases if needed (currently not used)
-- CREATE DATABASE meutch_integration;
-- CREATE DATABASE meutch_functional;

-- Set up any additional test-specific configuration
-- ALTER DATABASE meutch_dev SET timezone = 'UTC';
