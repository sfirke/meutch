"""Shared helpers for API integration tests."""


def auth_headers(token):
    """Return Authorization headers for a bearer token."""
    return {"Authorization": f"Bearer {token}"}


def login_api_user(client, email, password="testpassword123"):
    """Authenticate through the API and return the access token."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )

    assert response.status_code == 200
    return response.get_json()["access_token"]
