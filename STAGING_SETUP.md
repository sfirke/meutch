# Meutch Staging Environmen### Environment Variables Setup

**Important**: Environment variables must be set in the DigitalOcean Web UI, not in the app spec file. The app spec should only define the service structure.

Set these in DigitalOcean App Platform for your staging app:

```bash
# Core Configuration
FLASK_ENV=staging
SECRET_KEY=<generate-with-secrets.token_hex(32)>

# Database (staging database)
DATABASE_URL=postgresql://user:pass@staging-db.ondigitalocean.com:25060/meutch_staging

# File Storage
DO_SPACES_REGION=nyc3
DO_SPACES_KEY=<same-as-prod>
DO_SPACES_SECRET=<same-as-prod>
DO_SPACES_BUCKET=<same-as-prod-or-separate-staging-bucket>

# Email
MAILGUN_API_KEY=<same-as-prod>
MAILGUN_DOMAIN=<same-as-prod-or-staging-domain>
```nt outlines the staging environment setup for the Meutch application, including database management, deployment pipeline, and development workflow.

## Overview

The staging environment provides a production-like testing environment with real data (anonymized), allowing for thorough testing before deploying to production.

## Branch Strategy

- **`main`** → Production environment (auto-deploy)
- **`staging`** → Staging environment (auto-deploy, production-like data)
- **Feature branches** → merge to `staging` for testing → merge to `main`

## Architecture

```
Production DB (DigitalOcean) ─sync─> Staging DB (DigitalOcean)
         ↓                                    ↓
   Production App                      Staging App
      (main branch)                  (staging branch)
```

## Environment Configuration

### Staging Environment Variables

Set these in DigitalOcean App Platform for your staging app:

```bash
# Core Configuration
FLASK_ENV=staging
SECRET_KEY=<generate-with-secrets.token_hex(32)>

# Database (staging database)
DATABASE_URL=postgresql://user:pass@staging-db.ondigitalocean.com:25060/meutch_staging

# File Storage (optional separate bucket)
DO_SPACES_REGION=nyc3
DO_SPACES_KEY=<same-as-prod>
DO_SPACES_SECRET=<same-as-prod>
STAGING_DO_SPACES_BUCKET=meutch-staging  # Optional separate bucket

# Email (optional separate domain)
MAILGUN_API_KEY=<same-as-prod>
STAGING_MAILGUN_DOMAIN=staging.yourdomain.com  # Optional separate domain
```

### GitHub Secrets

Add these secrets to your GitHub repository:

```bash
# DigitalOcean
DIGITALOCEAN_ACCESS_TOKEN=<your-do-token>
STAGING_APP_ID=<your-staging-app-id>
STAGING_APP_URL=meutch-staging.ondigitalocean.app

# Database URLs
PRODUCTION_DATABASE_URL=<production-database-url>
STAGING_DATABASE_URL=<staging-database-url>
```

## Database Management

### Philosophy: Exact Production Replica

**Staging uses REAL production data** - no anonymization or synthetic data. This approach:
- ✅ Provides authentic testing scenarios
- ✅ Catches real-world edge cases
- ✅ Tests with actual user behavior patterns
- ✅ Validates against real data volumes
- ⚠️ Requires production-level security controls

This is the industry standard for companies like Facebook, Google, Netflix, etc.

### Creating the Staging Database

1. **Create a new database** in DigitalOcean:
   ```bash
   # Name: meutch-staging
   # Engine: PostgreSQL 17
   # Size: Same as production (for performance testing)
   ```

2. **Get the connection string** and set as `DATABASE_URL` in the staging app

### Syncing Production Data to Staging

Use the provided sync script to create an exact copy of production:

```bash
# Set environment variables
export DATABASE_URL="postgresql://prod-user:pass@prod-db:25060/meutch"
export STAGING_DATABASE_URL="postgresql://staging-user:pass@staging-db:25060/meutch_staging"

# Run sync (creates exact production replica)
python sync_staging_db.py
```

The sync script:
- ✅ Creates exact copy of all production data
- ✅ Preserves all relationships and data integrity  
- ✅ Maintains realistic data volumes and patterns
- ✅ **No data modifications** - true production replica
- ⚠️ Contains real user data (requires security controls)

### Manual Database Operations

```bash
# Connect to staging database
psql $STAGING_DATABASE_URL

# Run migrations on staging
export FLASK_ENV=staging
flask db upgrade

# Seed staging-specific data
flask seed data --env staging
```

## Deployment Pipeline

### Automatic Deployment

1. **Push to staging branch** triggers automatic deployment
2. **GitHub Actions** runs tests first
3. **If tests pass**, deploys to DigitalOcean staging app
4. **Runs database migrations** automatically
5. **App becomes available** at staging URL

### Manual Deployment

Trigger manual deployment via GitHub Actions:
1. Go to Actions tab in GitHub
2. Select "Deploy to Staging" workflow
3. Click "Run workflow" → select staging branch
4. Optionally enable data sync from production

## Development Workflow

### Working with Staging

1. **Create feature branch** from `main`:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/my-new-feature
   ```

2. **Develop and test locally**:
   ```bash
   # Local development
   export FLASK_ENV=development
   flask run
   ```

3. **Test in staging**:
   ```bash
   # Push to staging for testing
   git checkout staging
   git merge feature/my-new-feature
   git push origin staging
   
   # Wait for auto-deployment, then test at:
   # https://meutch-staging.ondigitalocean.app
   ```

4. **Deploy to production**:
   ```bash
   # After staging testing passes
   git checkout main
   git merge feature/my-new-feature
   git push origin main
   ```

### Testing in Staging

- **URL**: https://meutch-staging.ondigitalocean.app
- **Data**: Exact copy of production data (real users, items, interactions)
- **Authentication**: Use real user credentials from production
- **Testing approach**: Test features with real-world data patterns

### Security Requirements

**⚠️ CRITICAL: Staging contains real production data**

1. **Access Control**:
   - Only authorized team members should have staging access
   - Consider VPN or IP whitelisting for staging environment
   - Use strong authentication (2FA recommended)
   - Audit and monitor staging access

2. **Data Handling**:
   - Treat staging data with same security as production
   - No downloading or exporting of staging data
   - Regular security reviews of staging access
   - Data retention policies should match production

3. **Network Security**:
   - Staging should be on private network if possible
   - Regular security scans and updates
   - Monitor for unusual access patterns

4. **Development Practices**:
   - Never commit staging credentials to version control
   - Use environment variables for all sensitive config
   - Regular rotation of staging database credentials

## Monitoring & Maintenance

### Health Checks

- **Staging health**: https://meutch-staging.ondigitalocean.app/health
- **Database status**: `flask seed status` (shows record counts)

### Regular Maintenance

1. **Weekly data refresh** (recommended):
   ```bash
   # Refresh staging with latest production data
   python sync_staging_db.py
   ```

2. **Monthly cleanup**:
   - Review staging resource usage
   - Clean up old test data if needed
   - Update staging environment variables

### Troubleshooting

**Common Issues:**

1. **Staging app won't start**:
   - Check environment variables are set
   - Verify `DATABASE_URL` is correct
   - Check app logs in DigitalOcean dashboard

2. **Database connection issues**:
   - Verify database is running and accessible
   - Check connection string format
   - Ensure database user has proper permissions

3. **Data sync fails**:
   - Verify both database URLs are accessible
   - Check `pg_dump` and `psql` are available
   - Ensure sufficient disk space for dump file

**Checking logs:**
```bash
# DigitalOcean App Platform logs
doctl apps logs $STAGING_APP_ID

# Local database sync output provides details
python sync_staging_db.py
```

## Security Notes

- **Staging contains REAL production data** - not anonymized or synthetic
- **Same security requirements as production** apply to staging
- **Access should be restricted** to authorized team members only
- **Consider network isolation** - VPN, IP whitelisting, private networking
- **Audit staging access** and monitor for unusual activity
- **Data governance policies** should cover staging environment
- **Regular security reviews** should include staging infrastructure

## Development Notes

- **Local development** should use Docker test database + seeded data
- **Staging** should use production data copy for authentic testing
- **Seeding functionality** is retained for local development only
- **Production data sync** is the recommended approach for staging

## Cost Optimization

- **Staging database** can be smaller than production
- **Consider pausing** staging app during off-hours if supported
- **Share DigitalOcean Spaces bucket** with production (different prefixes)
- **Use staging-specific email domain** to avoid deliverability issues

## Deployment Status

✅ **Staging Environment Successfully Deployed!**

- **URL**: https://meutch-staging.ondigitalocean.app
- **Status**: Active and running
- **Database**: Connected and migrated
- **Environment**: Staging configuration active

## Next Steps

1. **Set up DigitalOcean staging app** using `.do/staging-app.yaml`
2. **Configure GitHub secrets** for automated deployment  
3. **Create staging database** and set connection string
4. **Run initial data sync** from production
5. **Test the complete workflow** with a small feature

## Support

For issues with staging environment:
1. Check this documentation first
2. Review DigitalOcean app and database logs
3. Test database connectivity manually
4. Verify GitHub Actions are running correctly
