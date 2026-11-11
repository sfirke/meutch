"""The vocabulary of activity-log events.

Kept separate from ``app.utils.activity_log`` so the read side and the tests can import
the names without pulling in the writer.

Deliberately plain string constants rather than an Enum or a database CHECK constraint:
a constraint violation would *lose* the event. An unregistered event type logs a warning
and still writes its row.
"""

AUTH_LOGIN_SUCCEEDED = "auth.login.succeeded"
AUTH_LOGIN_FAILED = "auth.login.failed"
AUTH_LOGIN_BLOCKED = "auth.login.blocked"
AUTH_LOGIN_REJECTED_UNCONFIRMED = "auth.login.rejected_unconfirmed"
AUTH_LOGOUT = "auth.logout"
AUTH_ACCOUNT_LOCKED = "auth.account.locked"
AUTH_REGISTER_SUCCEEDED = "auth.register.succeeded"
AUTH_REGISTER_BLOCKED = "auth.register.blocked"
AUTH_EMAIL_CONFIRMED = "auth.email.confirmed"
AUTH_PASSWORD_RESET_REQUESTED = "auth.password_reset.requested"
AUTH_PASSWORD_RESET_COMPLETED = "auth.password_reset.completed"
AUTH_TOKEN_REUSE_DETECTED = "auth.token.reuse_detected"
PROFILE_NAME_CHANGED = "profile.name.changed"

EVENT_TYPES = frozenset(
    {
        AUTH_LOGIN_SUCCEEDED,
        AUTH_LOGIN_FAILED,
        AUTH_LOGIN_BLOCKED,
        AUTH_LOGIN_REJECTED_UNCONFIRMED,
        AUTH_LOGOUT,
        AUTH_ACCOUNT_LOCKED,
        AUTH_REGISTER_SUCCEEDED,
        AUTH_REGISTER_BLOCKED,
        AUTH_EMAIL_CONFIRMED,
        AUTH_PASSWORD_RESET_REQUESTED,
        AUTH_PASSWORD_RESET_COMPLETED,
        AUTH_TOKEN_REUSE_DETECTED,
        PROFILE_NAME_CHANGED,
    }
)

# Human-readable names for the admin Activity page. A row whose event type is missing
# here still renders -- see `activity_event_label` in app/template_filters.py -- so a
# rolling deploy or a reverted branch never produces a blank cell.
EVENT_LABELS = {
    AUTH_LOGIN_SUCCEEDED: "Signed in",
    AUTH_LOGIN_FAILED: "Sign-in failed",
    AUTH_LOGIN_BLOCKED: "Sign-in blocked (locked out)",
    AUTH_LOGIN_REJECTED_UNCONFIRMED: "Sign-in refused (email unconfirmed)",
    AUTH_LOGOUT: "Signed out",
    AUTH_ACCOUNT_LOCKED: "Account locked",
    AUTH_REGISTER_SUCCEEDED: "Registered",
    AUTH_REGISTER_BLOCKED: "Registration blocked (bot check)",
    AUTH_EMAIL_CONFIRMED: "Email confirmed",
    AUTH_PASSWORD_RESET_REQUESTED: "Password reset requested",
    AUTH_PASSWORD_RESET_COMPLETED: "Password reset completed",
    AUTH_TOKEN_REUSE_DETECTED: "API refresh token replayed",
    PROFILE_NAME_CHANGED: "Name changed",
}

# The only context keys each event may store; anything else is dropped. Each key is a
# deliberate privacy decision -- do not add one without making it.
EVENT_CONTEXT_KEYS = {
    # The address exactly as typed is what lets support see that a member has been
    # signing in as sam@gmial.com. The privacy policy covers it, and it is deleted with
    # the rest of the row at the end of the retention window.
    AUTH_LOGIN_FAILED: frozenset({"attempted_email", "account_exists"}),
    AUTH_PASSWORD_RESET_REQUESTED: frozenset(
        {"attempted_email", "account_exists", "notification_sent"}
    ),
    AUTH_LOGIN_BLOCKED: frozenset({"retry_after_minutes"}),
    AUTH_ACCOUNT_LOCKED: frozenset({"lockout_count"}),
    AUTH_REGISTER_SUCCEEDED: frozenset({"location_method"}),
    # The address lets support find a real person the bot checks turned away, and the
    # names as typed show whether the name check caught a real one.
    AUTH_REGISTER_BLOCKED: frozenset(
        {
            "reason",
            "name_check",
            "attempted_email",
            "attempted_first_name",
            "attempted_last_name",
        }
    ),
    AUTH_TOKEN_REUSE_DETECTED: frozenset({"reason"}),
    # The old name exists nowhere else once it is changed, and it is what shows who a
    # renamed account used to be.
    PROFILE_NAME_CHANGED: frozenset(
        {"old_first_name", "old_last_name", "new_first_name", "new_last_name"}
    ),
}
