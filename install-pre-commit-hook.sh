#!/bin/bash

# Script to install the pre-commit hook
# Run this script to set up automatic testing before commits

set -e

HOOK_SOURCE="pre-commit-hook"
HOOK_DEST=".git/hooks/pre-commit"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_color() {
    printf "${1}${2}${NC}\n"
}

print_color $BLUE "🔧 Installing pre-commit hook..."

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    print_color $RED "❌ Not in a git repository. Please run this from the project root."
    exit 1
fi

# Check if hook source exists
if [ ! -f "$HOOK_SOURCE" ]; then
    print_color $RED "❌ Pre-commit hook source file not found: $HOOK_SOURCE"
    exit 1
fi

# Create hooks directory if it doesn't exist
mkdir -p ".git/hooks"

# Check if hook already exists
if [ -f "$HOOK_DEST" ]; then
    print_color $YELLOW "⚠️  Pre-commit hook already exists. Creating backup..."
    cp "$HOOK_DEST" "$HOOK_DEST.backup.$(date +%Y%m%d_%H%M%S)"
fi

# Install the hook
cp "$HOOK_SOURCE" "$HOOK_DEST"
chmod +x "$HOOK_DEST"

print_color $GREEN "✅ Pre-commit hook installed successfully!"
print_color $BLUE "📝 The hook will now run unit tests before each commit."
print_color $BLUE "💡 To bypass the hook for a specific commit, use: git commit --no-verify"

# Test the hook
print_color $BLUE "🧪 Testing the hook installation..."
if [ -x "$HOOK_DEST" ]; then
    print_color $GREEN "✅ Hook is executable and ready to use!"
else
    print_color $RED "❌ Hook installation failed - not executable."
    exit 1
fi

print_color $GREEN "🎉 Installation complete!"
