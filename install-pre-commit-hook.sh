#!/bin/bash

# Script to install pre-commit managed hooks for the repository
# Run this script after installing requirements-dev.txt

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_color() {
    printf "${1}${2}${NC}\n"
}

print_color $BLUE "🔧 Installing pre-commit hooks..."

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    print_color $RED "❌ Not in a git repository. Please run this from the project root."
    exit 1
fi

# Check if pre-commit is available
if ! command -v pre-commit > /dev/null 2>&1; then
    print_color $RED "❌ pre-commit is not installed in the current environment."
    print_color $YELLOW "💡 Activate your venv and run: pip install -r requirements-dev.txt"
    exit 1
fi

print_color $BLUE "🪝 Installing Git hooks for pre-commit and pre-push..."
pre-commit install --hook-type pre-commit --hook-type pre-push

print_color $BLUE "📦 Preparing hook environments..."
pre-commit install-hooks

print_color $BLUE "🧪 Validating the configuration..."
if ! pre-commit validate-config > /dev/null; then
    print_color $RED "❌ pre-commit configuration is invalid."
    exit 1
fi

print_color $GREEN "✅ Pre-commit hooks installed successfully!"
print_color $BLUE "📝 Commits now run fast file-scoped linting; pushes run the Alembic check and unit tests."
print_color $BLUE "💡 To run hooks manually: pre-commit run --all-files"
print_color $BLUE "💡 To bypass a hook for a specific commit, use: git commit --no-verify"
print_color $GREEN "🎉 Installation complete!"
