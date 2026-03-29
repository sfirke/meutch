"""Functional tests for error handlers and custom error pages."""
import pytest
from flask import url_for


class TestCustomErrorPages:
    """Test custom error page handlers."""

    def test_custom_404_page_renders(self, client):
        """Test that a 404 error renders the custom 404 page."""
        response = client.get('/nonexistent-page-that-does-not-exist')
        
        assert response.status_code == 404
        assert b'Page Not Found' in response.data
        assert b'Looks like this page wandered off' in response.data
        assert b'Go Home' in response.data

    def test_404_page_has_home_link(self, client, app):
        """Test that the 404 page links back to the home page."""
        response = client.get('/this-does-not-exist')
        
        assert response.status_code == 404
        # Check that the home URL is in the response
        with app.app_context():
            home_url = url_for('main.index')
        assert home_url.encode() in response.data
