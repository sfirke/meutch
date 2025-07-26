#!/usr/bin/env python3
"""
Database sync utility for staging environment.

Creates an exact copy of production data in staging for authentic testing.
Run with: python sync_staging_db.py

SECURITY NOTE: Staging will contain real production data and should be treated
with the same security controls as production.
"""

import os
import sys
import subprocess
import click
from datetime import datetime
from urllib.parse import urlparse

@click.command()
def sync_staging_db():
    """Create exact copy of production database in staging for authentic testing."""
    
    # Get database URLs
    prod_db_url = os.environ.get('DATABASE_URL')
    staging_db_url = os.environ.get('STAGING_DATABASE_URL')
    
    if not prod_db_url:
        click.echo("❌ ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    if not staging_db_url:
        click.echo("❌ ERROR: STAGING_DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Parse URLs for basic validation
    prod_parsed = urlparse(prod_db_url)
    staging_parsed = urlparse(staging_db_url)
    
    if prod_parsed.scheme not in ['postgresql', 'postgres']:
        click.echo("❌ ERROR: Only PostgreSQL databases are supported")
        sys.exit(1)
    
    # Safety check
    if 'production' in staging_db_url.lower() or 'prod' in staging_db_url.lower():
        click.echo("❌ ERROR: Staging database URL appears to point to production!")
        sys.exit(1)
    
    click.echo("� Syncing production data to staging...")
    
    # Create dump file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dump_file = f"/tmp/prod_dump_{timestamp}.sql"
    
    try:
        # Create production dump
        click.echo("📦 Creating production dump...")
        dump_cmd = [
            'pg_dump', prod_db_url,
            '--no-owner', '--no-privileges', '--clean', '--if-exists',
            '--file', dump_file
        ]
        
        result = subprocess.run(dump_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            click.echo(f"❌ ERROR creating dump: {result.stderr}")
            sys.exit(1)
        
        # Restore to staging
        click.echo("📥 Restoring to staging...")
        restore_cmd = ['psql', staging_db_url, '--file', dump_file, '--quiet']
        
        result = subprocess.run(restore_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            click.echo(f"❌ ERROR restoring: {result.stderr}")
            sys.exit(1)
        
        # Staging sync complete - no data modifications needed
        # Staging maintains exact replica of production data
        
        click.echo("✅ Production data synced to staging successfully!")
        
    except KeyboardInterrupt:
        click.echo("\n⚠️  Sync interrupted")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ ERROR: {str(e)}")
        sys.exit(1)
    finally:
        # Clean up
        if os.path.exists(dump_file):
            os.remove(dump_file)


if __name__ == '__main__':
    sync_staging_db()
