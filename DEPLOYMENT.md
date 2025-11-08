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
```

### Optional: Email Allowlist (Staging/Testing)

To prevent staging environments from sending emails to real users, configure an allowlist:

```bash
# Comma-separated list of allowed email addresses
EMAIL_ALLOWLIST=test1@example.com,test2@example.com
```

When `EMAIL_ALLOWLIST` is set:
- ✅ Only listed addresses will receive emails
- ✅ All other email attempts are logged but blocked
- ✅ Scheduled jobs (loan reminders) run normally but respect the allowlist
- ✅ Perfect for staging with production data copies

**Important:** Leave `EMAIL_ALLOWLIST` unset or empty in production to send emails to all users.

## Loan Reminder System

Meutch includes an automated system to send email reminders for loans:
- **3-day reminder**: Sent when a loan is 3 days from due
- **Due date reminder**: Sent to borrower and owner on the due date
- **Overdue reminders**: Sent on days 1, 3, 7, and 14 after the due date

### Configuration Requirements

The loan reminder system requires `SERVER_NAME` and `PREFERRED_URL_SCHEME` to be set. Without these, `url_for(_external=True)` cannot build URLs outside of a request context (CLI execution, scheduled jobs), and the command will fail with:

```
Unable to build URLs outside an active request without 'SERVER_NAME' configured.
```

### Running Manually

To test or manually trigger the reminder system:

```bash
flask check-loan-reminders
```

This processes all approved loans and sends appropriate reminders based on due dates.

### Automated Scheduling

#### DigitalOcean App Platform

Configure a scheduled job in your app spec:

```yaml
jobs:
  - name: loan-reminders
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

## Additional Resources

- [Flask Deployment Documentation](https://flask.palletsprojects.com/en/latest/deploying/)
- [DigitalOcean App Platform Documentation](https://docs.digitalocean.com/products/app-platform/)
- [Mailgun Documentation](https://documentation.mailgun.com/)
