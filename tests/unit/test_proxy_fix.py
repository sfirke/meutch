"""Tests for trusting the platform proxy's forwarded headers.

The app runs behind a load balancer, so ``request.remote_addr`` is the proxy
unless ProxyFix is wired up. That matters beyond cosmetics: the rate limiter
keys on the caller's address, so without this every client shares one bucket.

The important assertion here is that the *rightmost* forwarded address wins.
``X-Forwarded-For`` is appended to by each hop, so the leftmost entry is
whatever the client sent -- trusting it lets anyone spoof their own IP.
"""

from flask import request
from flask_limiter.util import get_remote_address

from app import create_app
from conftest import TestConfig


def _build_app(trusted_proxy_count):
    """Create an app with a given proxy trust level and a probe route."""

    class ProxyConfig(TestConfig):
        TRUSTED_PROXY_COUNT = trusted_proxy_count

    app = create_app(ProxyConfig)

    @app.route("/_test/client-info")
    def client_info():
        return {
            "remote_addr": request.remote_addr,
            "limiter_key": get_remote_address(),
            "scheme": request.scheme,
        }

    return app


class TestTrustedProxyCount:
    """request.remote_addr reflects the client, not the proxy."""

    def test_one_trusted_hop_uses_rightmost_forwarded_address(self):
        """A client-supplied leftmost X-Forwarded-For entry must be ignored.

        With one trusted proxy, the only address the proxy itself vouches for is
        the last one it appended. Anything to the left of it was supplied by the
        caller and is not evidence of anything.
        """
        app = _build_app(1)
        client = app.test_client()

        response = client.get(
            "/_test/client-info",
            headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"},
        )

        assert response.status_code == 200
        assert response.json["remote_addr"] == "5.6.7.8"

    def test_single_forwarded_address_is_used(self):
        """The ordinary case: one proxy, one appended address."""
        app = _build_app(1)
        client = app.test_client()

        response = client.get(
            "/_test/client-info",
            headers={"X-Forwarded-For": "203.0.113.10"},
        )

        assert response.json["remote_addr"] == "203.0.113.10"

    def test_rate_limiter_key_follows_the_client_address(self):
        """The limiter buckets per client, not per proxy."""
        app = _build_app(1)
        client = app.test_client()

        first = client.get("/_test/client-info", headers={"X-Forwarded-For": "203.0.113.10"})
        second = client.get("/_test/client-info", headers={"X-Forwarded-For": "203.0.113.11"})

        assert first.json["limiter_key"] == "203.0.113.10"
        assert second.json["limiter_key"] == "203.0.113.11"

    def test_forwarded_proto_is_trusted(self):
        """url_for and redirects need the scheme the client actually used."""
        app = _build_app(1)
        client = app.test_client()

        response = client.get(
            "/_test/client-info",
            headers={"X-Forwarded-For": "203.0.113.10", "X-Forwarded-Proto": "http"},
        )

        assert response.json["scheme"] == "http"

    def test_zero_trusted_proxies_ignores_forwarded_headers(self):
        """With no proxy in front, forwarded headers are attacker input."""
        app = _build_app(0)
        client = app.test_client()

        response = client.get(
            "/_test/client-info",
            headers={"X-Forwarded-For": "1.2.3.4", "X-Forwarded-Proto": "http"},
        )

        assert response.json["remote_addr"] == "127.0.0.1"
        # The test client's own base URL is https, so an ignored X-Forwarded-Proto
        # of http leaves the scheme untouched.
        assert response.json["scheme"] == "https"
