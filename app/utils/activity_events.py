"""The vocabulary of activity-log events.

Kept separate from ``app.utils.activity_log`` so the read side, the tests and the
call-site linter can import the names without pulling in the writer.

Event names are plain module-level string constants, matching the style of
``auth_service.LOGIN_STATUS_*``. They are deliberately not an Enum (every call site
and assertion would grow a ``.value``, and a raw string would still slip through) and
deliberately not a database CHECK constraint: a constraint violation would *lose* the
event, which is the opposite of what an audit log should do under stress. An
unregistered event type logs a warning and still writes its row.
"""

AUTH_LOGIN_SUCCEEDED = "auth.login.succeeded"
AUTH_LOGIN_FAILED = "auth.login.failed"
AUTH_LOGIN_BLOCKED = "auth.login.blocked"
AUTH_LOGIN_REJECTED_UNCONFIRMED = "auth.login.rejected_unconfirmed"
AUTH_LOGOUT = "auth.logout"
AUTH_ACCOUNT_LOCKED = "auth.account.locked"
AUTH_REGISTER_SUCCEEDED = "auth.register.succeeded"
AUTH_EMAIL_CONFIRMED = "auth.email.confirmed"
AUTH_PASSWORD_RESET_REQUESTED = "auth.password_reset.requested"
AUTH_PASSWORD_RESET_COMPLETED = "auth.password_reset.completed"
AUTH_TOKEN_REUSE_DETECTED = "auth.token.reuse_detected"

EVENT_TYPES = frozenset(
    {
        AUTH_LOGIN_SUCCEEDED,
        AUTH_LOGIN_FAILED,
        AUTH_LOGIN_BLOCKED,
        AUTH_LOGIN_REJECTED_UNCONFIRMED,
        AUTH_LOGOUT,
        AUTH_ACCOUNT_LOCKED,
        AUTH_REGISTER_SUCCEEDED,
        AUTH_EMAIL_CONFIRMED,
        AUTH_PASSWORD_RESET_REQUESTED,
        AUTH_PASSWORD_RESET_COMPLETED,
        AUTH_TOKEN_REUSE_DETECTED,
    }
)

# Context keys permitted past the PII denylist, for specific events only.
# Each entry is a deliberate privacy decision -- do not add to this without one.
CONTEXT_KEY_EXEMPTIONS = {
    # Support: the address exactly as typed is what lets us see that a member has been
    # signing in as sam@gmial.com. Recorded whether or not it matches an account, and
    # deleted along with the rest of the row at the end of the retention window. The
    # privacy policy says so in as many words.
    AUTH_LOGIN_FAILED: frozenset({"attempted_email"}),
    AUTH_PASSWORD_RESET_REQUESTED: frozenset({"attempted_email"}),
}
