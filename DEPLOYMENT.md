# Meutch Deployment Guide

This document provides deployment instructions for Meutch. Mostly written for the flagship instance at [https://www.meutch.com](https://www.meutch.com), but applicable to anyone else deploying their own instance.

## Environment Configuration

### Required Environment Variables

All deployments require these core variables:

```bash
# Flask
SECRET_KEY=<generate-with-secrets.token_hex(32)>
FLASK_APP=app.py
FLASK_ENV=production  # or 'staging' for staging environment

# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Storage Backend
STORAGE_BACKEND=digitalocean  # or 'local' for file system storage

# URL Building (Required for CLI and scheduled jobs, i.e., overdue email reminders)
# IMPORTANT: Include the scheme (http:// or https://) in SERVER_NAME
# Use http://localhost:5000 for local development
SERVER_NAME=https://your-domain.com  # e.g., https://meutch.com
```

### Optional: DigitalOcean Spaces (if STORAGE_BACKEND=digitalocean)

```bash
DO_SPACES_REGION=nyc3
DO_SPACES_KEY=<your-spaces-key>
DO_SPACES_SECRET=<your-spaces-secret>
DO_SPACES_BUCKET=<your-bucket-name>
```

### Optional: Email (Mailgun)

```bash
MAILGUN_API_KEY=<your-mailgun-api-key>
MAILGUN_DOMAIN=<your-mailgun-domain>
MAILGUN_WEBHOOK_SIGNING_KEY=<your-mailgun-webhook-signing-key>

# Only needed when sharing a single Mailgun domain across environments
# (e.g. both staging and prod use replies@meutch.com).
# Set to "staging-" on staging so Mailgun routes can distinguish.
MAILGUN_REPLY_PREFIX=staging-
```

For reply-by-email, configure a Mailgun inbound route that forwards parsed messages to:

```text
https://your-domain.com/webhooks/mailgun/messages
```

**Multi-environment setup with a single Mailgun domain:** Use `MAILGUN_REPLY_PREFIX`
to encode the environment in the reply-to local part:

- Production: `reply+{uuid}@meutch.com` (no prefix)
- Staging:   `reply+staging-{uuid}@meutch.com`

Create two Mailgun routes on the same domain (routes are free):

1. `match_recipient("reply\+staging-.*@meutch.com")` → forward to `https://staging.meutch.com/webhooks/mailgun/messages`
2. `match_recipient("reply\+.*@meutch.com")` → forward to `https://meutch.com/webhooks/mailgun/messages`

Route order matters — put the more specific `staging-` rule first.

### Optional: Mobile API JWT Auth

The web app still uses Flask-Login sessions. These variables configure the parallel JWT auth surface under `/api/v1/auth` for mobile clients.

```bash
# Recommended: separate signing secret for API JWTs
JWT_SECRET_KEY=<generate-with-secrets.token_hex(32)>

# Token lifetimes
JWT_ACCESS_TOKEN_EXPIRES_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRES_DAYS=30
```

Operational notes:
- Access tokens are sent as `Authorization: Bearer <token>` headers and should stay short-lived.
- Refresh tokens rotate on every successful `POST /api/v1/auth/refresh` call. Clients must replace the stored refresh token with the newly returned one each time.
- `POST /api/v1/auth/logout` revokes the whole current token family (session). Reusing an already-rotated refresh token also revokes that family and forces the user to log in again.
- If `JWT_SECRET_KEY` is unset, the app falls back to `SECRET_KEY`, but production deployments should set a dedicated JWT secret explicitly.

### Optional: API Rollout Controls And Rate Limiting

These variables harden the `/api/v1` surface for mobile clients and give deploys an operational rollback path without removing routes from the codebase.

```bash
# Emergency kill switch for the whole versioned API surface.
# When false, /api/v1/health still answers 200 with status=disabled.
API_V1_ENABLED=true

# Emergency read-only mode for non-auth mutations.
# When false, GETs plus /api/v1/auth/* remain available and other writes return 503.
API_V1_WRITE_ENABLED=true

# API-specific limiter toggle.
API_V1_RATE_LIMITS_ENABLED=true

# Strongly recommended for production and staging when using multiple workers or instances.
RATELIMIT_STORAGE_URI=redis://redis:6379/0

# Default endpoint-family limits.
API_V1_AUTH_LOGIN_RATE_LIMIT=10 per minute
API_V1_AUTH_REGISTER_RATE_LIMIT=5 per hour
API_V1_AUTH_RECOVERY_RATE_LIMIT=5 per hour
API_V1_AUTH_SESSION_RATE_LIMIT=60 per minute
API_V1_WRITE_RATE_LIMIT=30 per minute
API_V1_IMAGE_WRITE_RATE_LIMIT=10 per minute
```

Operational notes:
- API responses now include `X-Request-ID`. If a client sends its own `X-Request-ID`, the API echoes it back so application logs and client-side error reports can be correlated.
- `/api/v1/health` reports `ok`, `read_only`, or `disabled` so deploy checks can distinguish normal traffic, emergency read-only mode, and a full API shutdown.
- `memory://` limiter storage is process-local. It is acceptable for local development and isolated test runs, but it will not enforce a shared bucket across multiple Gunicorn workers or multiple app instances.
- Use Redis-backed limiter storage whenever staging or production can run more than one worker or instance.

### Optional: Digest Scheduler Timezone

Digest cadence boundaries are evaluated in one app timezone. The scheduler now prefers `TZ` (same timezone setting used by the server/runtime), then falls back to `DIGEST_TIMEZONE`, then UTC.

```bash
# Preferred: server/runtime timezone
TZ=America/New_York

# Backward-compatible fallback (used when TZ is missing/invalid)
DIGEST_TIMEZONE=America/New_York
```

### Optional: Email Allowlist (Staging/Testing)

To prevent staging environments from sending emails to real users, configure an allowlist:

```bash
# Comma-separated list of allowed email addresses
EMAIL_ALLOWLIST=test1@example.com,test2@example.com
```

When `EMAIL_ALLOWLIST` is set, only listed addresses will receive emails. All other email attempts are logged but blocked. This allows for selected testing while not spamming users with duplicated overdue notices, etc. that are already being sent from the production environment.

**Important:** Leave `EMAIL_ALLOWLIST` unset or empty in production to send emails to all users.

## Loan Reminder + Digest Job

Meutch includes one daily scheduled CLI job (`flask check-loan-reminders`) that now processes:

1. Loan reminder emails
2. Digest emails

Loan reminder behavior:
- **3-day reminder**: Sent when a loan is 3 days from due
- **Due date reminder**: Sent to borrower and owner on the due date
- **Overdue reminders**: Sent on days 1, 3, 7, and 14 after the due date

Digest cadence behavior:
- **daily** users: evaluated every day (including Sunday)
- **weekly** users: evaluated on Sunday only
- **none** users: skipped
- **Idempotency**: `digest_last_sent_at` is checked against cadence period boundary in resolved scheduler timezone (`TZ` first, then `DIGEST_TIMEZONE`, then UTC) and updated only after successful send
- **Fault isolation**: one user send failure does not abort the rest of the run


### Running Manually

To test or manually trigger the reminder system:

```bash
flask check-loan-reminders
```

This runs loan reminders and digest sends in the same execution flow.

### Automated Scheduling

#### DigitalOcean App Platform

Configure a scheduled job in your app spec:

```yaml
jobs:
  - name: loan-reminders-and-digests
    kind: SCHEDULED
    run_command: flask check-loan-reminders
    schedule: "0 9 * * *"  # Daily at 9 AM
    time_zone: America/New_York
    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
      - key: SECRET_KEY
        scope: RUN_TIME
      - key: MAILGUN_API_KEY
        scope: RUN_TIME
      - key: MAILGUN_DOMAIN
        scope: RUN_TIME
      - key: SERVER_NAME
        scope: RUN_TIME
      - key: TZ
        scope: RUN_TIME
      - key: DIGEST_TIMEZONE
        scope: RUN_TIME
```

Ensure all required environment variables are set in your DigitalOcean app configuration.

## Database Migrations

After deploying new code, always run migrations:

```bash
flask db upgrade
```

## Security Considerations

1. **SECRET_KEY**: Generate a cryptographically secure key. Never commit it to version control.
   ```bash
   python -c 'import secrets; print(secrets.token_hex(32))'
   ```

2. **Database**: Use strong passwords and restrict access to trusted IPs.

3. **HTTPS**: Always use HTTPS in production (set `SERVER_NAME=https://...`).

4. **Environment Variables**: Store sensitive values in your platform's secret management system, not in plain text files.
5. **JWT Secrets**: Rotate `JWT_SECRET_KEY` with the same care as `SECRET_KEY`. Changing it invalidates all outstanding API tokens immediately.
6. **API Rollout Flags**: Treat `API_V1_ENABLED`, `API_V1_WRITE_ENABLED`, and `API_V1_RATE_LIMITS_ENABLED` as operational controls; document any temporary override used during an incident and restore the defaults after the event.
7. **Limiter Storage**: Use a shared backend such as Redis for production or staging deployments with multiple workers or instances. In-memory limiter storage is not sufficient for that topology.

## Additional Resources

- [Flask Deployment Documentation](https://flask.palletsprojects.com/en/latest/deploying/)
- [DigitalOcean App Platform Documentation](https://docs.digitalocean.com/products/app-platform/)
- [Mailgun Documentation](https://documentation.mailgun.com/)
