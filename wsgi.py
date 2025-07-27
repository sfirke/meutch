#!/usr/bin/env python3
"""
WSGI entry point for staging deployment
"""

from app import create_app

# Create the Flask application instance
application = create_app()
app = application

if __name__ == "__main__":
    application.run(host='0.0.0.0', port=8080)
