#!/usr/bin/env python3
"""List users whose stored email would fail WTForms' Email() check under email_validator 2.x.

LoginForm, RegistrationForm, ForgotPasswordForm and ResendConfirmationForm all run
Email(), so a stored address that email_validator 2.x rejects would lock that user
out of login and password reset. Run this against production before deploying the
email_validator 1.1.3 -> 2.x upgrade.

Read-only: the session is opened with readonly=True and only SELECTs.

Usage (DATABASE_URL pointing at the database to check):
    uv run --with "email-validator==2.3.0" --with psycopg2-binary \
        python scripts/check_emails_email_validator_v2.py
or, in any environment that already has the upgraded requirements installed:
    python scripts/check_emails_email_validator_v2.py
"""

import os
import sys

import email_validator
import psycopg2
from email_validator import EmailNotValidError, validate_email


def main() -> int:
    major = int(email_validator.__version__.split(".")[0])
    if major < 2:
        print(f"email_validator {email_validator.__version__} is installed; this check needs 2.x.")
        return 2

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set.")
        return 2

    conn = psycopg2.connect(database_url)
    conn.set_session(readonly=True)
    try:
        with conn.cursor() as cur:
            # Deleted accounts are renamed to deleted_<id>@deleted.meutch and can't log in.
            cur.execute(
                "SELECT id, email, created_at FROM users WHERE NOT is_deleted ORDER BY created_at"
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    failures = []
    for user_id, email, created_at in rows:
        try:
            # Same arguments WTForms' Email() validator passes with its defaults.
            validate_email(
                email,
                check_deliverability=False,
                allow_smtputf8=True,
                allow_empty_local=False,
            )
        except EmailNotValidError as exc:
            failures.append((user_id, email, created_at, str(exc)))

    print(f"Checked {len(rows)} active users with email_validator {email_validator.__version__}.")
    if not failures:
        print("All stored emails pass. Safe to deploy the upgrade.")
        return 0

    print(f"{len(failures)} stored email(s) would be rejected:")
    for user_id, email, created_at, reason in failures:
        print(f"  {user_id}  {email!r}  (joined {created_at:%Y-%m-%d})  {reason}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
