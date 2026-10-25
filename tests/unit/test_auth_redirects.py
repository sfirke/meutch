"""Tests for the check on where the app may redirect after sign-in."""

import pytest

from app.auth.routes import _is_safe_url


class TestIsSafeUrl:
    @pytest.mark.parametrize(
        "target",
        [
            "/",
            "/profile",
            "/find?q=drill&page=2",
            "/find?q=cordless%20drill",
            "/requests/3f2b8c1e-5d47-4a9b-8e21-0c6d9f7a1b34/detail",
            "/share/giveaway/abc123",
            "/profile?tab=settings#digest",
            "/circles?next=https://example.com/",
        ],
    )
    def test_accepts_local_paths(self, target):
        assert _is_safe_url(target) is True

    @pytest.mark.parametrize(
        "target",
        [
            "",
            None,
            "profile",
            "//evil.com",
            "///evil.com",
            "////evil.com",
            "/\\evil.com",
            "/\\/evil.com",
            "\\\\evil.com",
            "\\evil.com",
            "/profile\\..\\evil.com",
            "https:evil.com",
            "https://evil.com",
            "http://evil.com/phishing",
            "http://localhost/profile",
            "javascript:alert(1)",
            "/\t/evil.com",
            "\t//evil.com",
            "/\n/evil.com",
            "/\r/evil.com",
            "/profile\r\nSet-Cookie: a=b",
            " //evil.com",
            " /profile",
            "/find?q=cordless drill",
            "/\x00/evil.com",
            "/\x0b/evil.com",
            "/\x7f/evil.com",
            "/\u2028/evil.com",
            "/\u00a0/evil.com",
        ],
    )
    def test_rejects_everything_else(self, target):
        assert _is_safe_url(target) is False
