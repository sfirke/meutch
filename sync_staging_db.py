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
    prod_db_url = os.environ.get('PROD_DATABASE_URL')
    staging_db_url = os.environ.get('STAGING_DATABASE_URL')
    
    if not prod_db_url:
        click.echo("❌ ERROR: PROD_DATABASE_URL environment variable not set")
        click.echo("   This should be the production database connection string")
        sys.exit(1)
    
    if not staging_db_url:
        click.echo("❌ ERROR: STAGING_DATABASE_URL environment variable not set")
        click.echo("   This should be the staging database connection string")
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
    
    click.echo("🔄 Syncing production data to staging...")
    
    # Verify production database has data before dumping
    click.echo("🔍 Verifying production database...")
    verify_cmd = ['psql', prod_db_url, '-t', '-c',
                  "SELECT COUNT(*) FROM users; SELECT COUNT(*) FROM item; SELECT COUNT(*) FROM user_web_links;"]
    verify_result = subprocess.run(verify_cmd, capture_output=True, text=True)
    
    if verify_result.returncode == 0:
        counts = [c.strip() for c in verify_result.stdout.strip().split('\n') if c.strip()]
        if len(counts) >= 3:
            click.echo(f"   Found {counts[0]} users, {counts[1]} items, {counts[2]} web links")
    else:
        click.echo(f"   ⚠️  Could not verify: {verify_result.stderr.splitlines()[0] if verify_result.stderr else 'Unknown error'}")
    
    # Create dump file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dump_file = f"/tmp/prod_dump_{timestamp}.sql"
    
    try:
        # Use PostgreSQL tools directly (both DBs are PostgreSQL 17)
        click.echo("📦 Creating production dump...")
        # Don't use --clean since we handle dropping tables ourselves with CASCADE
        dump_cmd = [
            'pg_dump', prod_db_url,
            '--no-owner', '--no-privileges',
            '--file', dump_file, '--verbose'
        ]
        
        result = subprocess.run(dump_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            click.echo(f"❌ ERROR creating dump: {result.stderr}")
            sys.exit(1)
        
        dump_size = os.path.getsize(dump_file)
        click.echo(f"📊 Created dump: {dump_size / 1024:.1f} KB")
        
        # Drop all tables in staging to ensure clean slate
        # This prevents foreign key constraint issues when restoring
        # The production dump will recreate everything including alembic_version
        click.echo("🧹 Cleaning staging database...")
        drop_cmd = ['psql', staging_db_url, '-t', '-c',
                   "SELECT 'DROP TABLE IF EXISTS \"' || tablename || '\" CASCADE;' "
                   "FROM pg_tables WHERE schemaname = 'public';"]
        drop_result = subprocess.run(drop_cmd, capture_output=True, text=True)
        
        if drop_result.returncode == 0 and drop_result.stdout.strip():
            # Execute the generated DROP statements
            execute_drops = ['psql', staging_db_url, '-c', drop_result.stdout]
            exec_result = subprocess.run(execute_drops, capture_output=True, text=True)
            if exec_result.returncode != 0:
                click.echo(f"⚠️  Warning during cleanup: {exec_result.stderr}")
        
        click.echo("📥 Restoring to staging...")
        # Remove --clean from restore since we already dropped everything
        restore_cmd = ['psql', staging_db_url, '--file', dump_file]
        
        result = subprocess.run(restore_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            click.echo(f"❌ ERROR restoring: {result.stderr}")
            sys.exit(1)
        
        # Verify restore succeeded
        count_cmd = ['psql', staging_db_url, '-t', '-c',
                    "SELECT COUNT(*) FROM users, COUNT(*) FROM item;"]
        count_result = subprocess.run(count_cmd, capture_output=True, text=True)
        
        if count_result.returncode == 0:
            counts = count_result.stdout.strip().split()
            if len(counts) >= 2:
                click.echo(f"📊 Staging now has {counts[0]} users, {counts[1]} items")
        
        # Show most recent data for verification
        click.echo("📊 Most recent user in staging:")
        recent_user_cmd = ['psql', staging_db_url, '-t', '-c',
                          "SELECT first_name, last_name, email, created_at FROM users ORDER BY created_at DESC LIMIT 1;"]
        recent_user_result = subprocess.run(recent_user_cmd, capture_output=True, text=True)
        
        if recent_user_result.returncode == 0 and recent_user_result.stdout.strip():
            click.echo(f"   {recent_user_result.stdout.strip()}")
        else:
            click.echo("   (unable to retrieve)")
        
        click.echo("📊 Most recent item in staging:")
        recent_item_cmd = ['psql', staging_db_url, '-t', '-c',
                          "SELECT name, created_at FROM item ORDER BY created_at DESC LIMIT 1;"]
        recent_item_result = subprocess.run(recent_item_cmd, capture_output=True, text=True)
        
        if recent_item_result.returncode == 0 and recent_item_result.stdout.strip():
            click.echo(f"   {recent_item_result.stdout.strip()}")
        else:
            click.echo("   (unable to retrieve)")
        
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
