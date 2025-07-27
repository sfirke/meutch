# Staging Environment Setup

This document outlines how to set up a staging environment for the Meutch application.

## Overview

The staging environment provides a production-like testing environment with real data synchronization, allowing for thorough testing before deploying to production.

## Branch Strategy

- **`main`** → Production environment (auto-deploy)
- **`staging`** → Staging environment (auto-deploy, production-like data)
- **Feature branches** → merge to `staging` for testing → merge to `main`

## Environment Configuration

### Required Environment Variables

For your staging deployment platform, configure these environment variables:

```bash
# Core Configuration
FLASK_ENV=staging
SECRET_KEY=<generate-secure-secret>
DATABASE_URL=<your-staging-database-url>

# Data Sync (for automatic production data sync)
PROD_DATABASE_URL=<your-production-database-url>
STAGING_DATABASE_URL=<your-staging-database-url>

# File Storage
DO_SPACES_REGION=<your-region>
DO_SPACES_KEY=<your-spaces-key>
DO_SPACES_SECRET=<your-spaces-secret>
DO_SPACES_BUCKET=<your-bucket-name>

# Email
MAILGUN_API_KEY=<your-mailgun-api-key>
MAILGUN_DOMAIN=<your-domain>
```

## Database Management

### Philosophy: Production Data Replica

The staging environment uses real production data (not anonymized) to provide authentic testing scenarios. This approach:
- ✅ Catches real-world edge cases
- ✅ Tests with actual user behavior patterns
- ✅ Validates against real data volumes
- ⚠️ Requires production-level security controls

### Automatic Data Sync

The staging environment automatically syncs production data during deployment:

1. **Production data is dumped** using `pg_dump`
2. **Staging database is restored** with production data
3. **No data modifications** - exact replica maintained
4. **Sync runs in background** to avoid deployment timeouts

### Manual Data Sync

You can also manually sync data using the provided script:

```bash
# Set environment variables
export PROD_DATABASE_URL="<your-production-db-url>"
export STAGING_DATABASE_URL="<your-staging-db-url>"

# Run sync
python sync_staging_db.py
```

## Deployment Pipeline

### Automatic Deployment

1. **Push to staging branch** triggers automatic deployment
2. **GitHub Actions** runs tests first
3. **Platform auto-deploys** if configured with `deploy_on_push`
4. **Runs database migrations** automatically
5. **Syncs production data** in background
6. **App becomes available** immediately

### Development Workflow

1. **Create feature branch** from `main`
2. **Develop and test locally**
3. **Merge to staging branch** for testing
4. **Test in staging environment**
5. **Merge to main** for production deployment

## Security Considerations

**⚠️ IMPORTANT: Staging contains real production data**

- Treat staging with the same security controls as production
- Restrict access to authorized team members only
- Consider network isolation (VPN, IP whitelisting)
- Regular security reviews should include staging
- Use strong authentication and monitoring

## Files Overview

- `startup-staging.sh` - Staging-specific startup script
- `sync_staging_db.py` - Production data sync utility
- `startup-wrapper.sh` - Environment-aware startup wrapper
- `.github/workflows/deploy-staging.yml` - CI/CD pipeline
- `wsgi.py` - WSGI entry point for production servers