-- Initialize the test database
-- This script runs when the Docker container starts

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create dedicated test database to isolate pytest from development data
CREATE DATABASE meutch_test;

-- Set up any additional test-specific configuration
-- ALTER DATABASE meutch_dev SET timezone = 'UTC';
