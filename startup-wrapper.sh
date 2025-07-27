#!/bin/bash
# Universal startup wrapper that chooses the right script based on environment

set -e

if [ "$FLASK_ENV" = "staging" ]; then
    echo "🚀 Starting staging environment..."
    exec ./startup-staging.sh
else
    echo "🚀 Starting production environment..."
    exec ./startup.sh
fi
