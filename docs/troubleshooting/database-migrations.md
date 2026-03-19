# Database Migrations Troubleshooting Guide

This guide covers common issues when working with database migrations and how to resolve them.

## Common Issues

### 1. Migration Fails to Apply

**Symptoms:**
- Migration script exits with an error
- Database changes are partially applied
- `MigrationError` exception raised

**Diagnosis:**
```bash
# Check migration status
python migrations/scripts/migrate.py --status

# Check PostgreSQL logs
tail -f /var/log/postgresql/postgresql-*.log

# Check for locks
SELECT * FROM pg_stat_activity WHERE state = 'active';
```

**Solutions:**

1. **Syntax Error in SQL**
   ```bash
   # Test the SQL manually
   psql $DATABASE_URL -f migrations/versions/XXX_migration.sql
   ```
   Fix any syntax errors in the migration file.

2. **Table/Column Already Exists**
   ```sql
   -- Use IF NOT EXISTS
   CREATE TABLE IF NOT EXISTS my_table (...);
   ALTER TABLE my_table ADD COLUMN IF NOT EXISTS new_column VARCHAR(100);
   ```

3. **Foreign Key Violation**
   - Ensure referenced tables exist before creating foreign keys
   - Check data integrity before adding constraints

4. **Transaction Timeout**
   ```bash
   # Increase statement timeout
   export MIGRATION_TIMEOUT=600000  # 10 minutes
   python migrations/scripts/migrate.py
   ```

### 2. Checksum Mismatch Error

**Symptoms:**
```
Migration error: Checksum verification failed:
  - Migration 003_add_search_vectors: checksum mismatch
```

**Cause:** A migration file was modified after it was applied.

**Solutions:**

1. **If the file was accidentally modified:**
   ```bash
   # Restore the original file from git
   git checkout HEAD -- migrations/versions/003_add_search_vectors.sql
   ```

2. **If the change was intentional:**
   ```bash
   # Skip verification (use with caution)
   python migrations/scripts/migrate.py --no-verify
   ```
   Then update the checksum in the database:
   ```sql
   -- Calculate new checksum and update
   UPDATE migrations_history
   SET checksum = 'new_checksum_here'
   WHERE version = '003';
   ```

3. **If you need to modify an applied migration:**
   Create a new migration instead of modifying the existing one.

### 3. Connection Refused

**Symptoms:**
```
asyncpg.exceptions.ConnectionRefused: connection refused
```

**Solutions:**

1. **Check PostgreSQL is running:**
   ```bash
   systemctl status postgresql
   # or
   pg_isready -h localhost -p 5432
   ```

2. **Verify connection string:**
   ```bash
   echo $DATABASE_URL
   psql $DATABASE_URL -c "SELECT 1"
   ```

3. **Check pg_hba.conf for access permissions**

### 4. Permission Denied

**Symptoms:**
```
asyncpg.exceptions.InsufficientPrivilegeError: permission denied
```

**Solutions:**

1. **Grant necessary permissions:**
   ```sql
   GRANT ALL PRIVILEGES ON DATABASE mind TO migration_user;
   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO migration_user;
   GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO migration_user;
   ```

2. **Use a superuser for migrations:**
   ```bash
   DATABASE_URL="postgresql://postgres:password@localhost/mind" \
   python migrations/scripts/migrate.py
   ```

### 5. Migration Hangs

**Symptoms:**
- Migration script doesn't complete
- No error message
- Database appears locked

**Diagnosis:**
```sql
-- Check for blocking queries
SELECT
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_query,
    blocking_activity.query AS blocking_query
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity
    ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.DATABASE IS NOT DISTINCT FROM blocked_locks.DATABASE
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity
    ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

**Solutions:**

1. **Terminate blocking queries:**
   ```sql
   SELECT pg_terminate_backend(blocking_pid);
   ```

2. **Wait for long-running transactions to complete**

3. **Use CONCURRENTLY for index creation:**
   ```sql
   CREATE INDEX CONCURRENTLY idx_name ON table_name(column);
   ```

### 6. Rollback Fails

**Symptoms:**
- `RollbackError` exception
- DOWN section missing or incomplete

**Solutions:**

1. **Missing DOWN section:**
   Add a DOWN section to the migration file:
   ```sql
   -- DOWN
   DROP TABLE IF EXISTS my_table CASCADE;
   ```

2. **Manual rollback required:**
   ```sql
   -- Connect to database
   psql $DATABASE_URL

   -- Manually execute rollback SQL
   DROP TABLE IF EXISTS problematic_table CASCADE;

   -- Remove from migration history
   DELETE FROM migrations_history WHERE version = 'XXX';
   ```

3. **Data loss prevention:**
   Before rolling back, backup affected data:
   ```sql
   CREATE TABLE backup_table AS SELECT * FROM table_to_drop;
   ```

## Recovery Procedures

### Recovering from Failed Migration

1. **Identify the state:**
   ```sql
   -- Check what was created
   SELECT table_name FROM information_schema.tables
   WHERE table_schema = 'public';

   -- Check migration history
   SELECT * FROM migrations_history ORDER BY version;
   ```

2. **Clean up partial changes:**
   ```sql
   -- If migration partially applied, clean up manually
   DROP TABLE IF EXISTS partial_table CASCADE;
   DROP INDEX IF EXISTS partial_index;
   ```

3. **Fix the migration and retry:**
   ```bash
   python migrations/scripts/migrate.py
   ```

### Recovering from Corrupted State

1. **Export current schema:**
   ```bash
   pg_dump -s $DATABASE_URL > schema_backup.sql
   ```

2. **Reset migrations history:**
   ```sql
   -- WARNING: Only if you're sure of current state
   TRUNCATE migrations_history;
   ```

3. **Re-record applied migrations:**
   ```sql
   INSERT INTO migrations_history (version, name, checksum)
   VALUES
     ('001', 'initial_schema', 'calculated_checksum'),
     ('002', 'add_auth_tables', 'calculated_checksum');
   ```

### Full Database Reset (Development Only)

```bash
# WARNING: Destroys all data
dropdb mind
createdb mind

# Re-run all migrations
python migrations/scripts/migrate.py
```

## Testing Migrations Locally

### Setting Up a Test Database

```bash
# Create test database
createdb mind_test

# Set environment
export DATABASE_URL="postgresql://localhost/mind_test"

# Run migrations
python migrations/scripts/migrate.py

# Test rollback
python migrations/scripts/rollback.py --count 1 --dry-run
python migrations/scripts/rollback.py --count 1

# Clean up
dropdb mind_test
```

### Using Docker for Isolation

```yaml
# docker-compose.test.yml
version: '3.8'
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: mind_test
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
    ports:
      - "5433:5432"
```

```bash
# Start test database
docker-compose -f docker-compose.test.yml up -d

# Run migrations against test database
DATABASE_URL="postgresql://test:test@localhost:5433/mind_test" \
python migrations/scripts/migrate.py

# Clean up
docker-compose -f docker-compose.test.yml down -v
```

### Automated Migration Testing

```python
# tests/test_migrations.py
import pytest
import asyncpg
from migrations.scripts.migrate import MigrationRunner
from migrations.scripts.rollback import RollbackRunner

@pytest.fixture
async def test_db():
    """Create a temporary test database."""
    conn = await asyncpg.connect("postgresql://localhost/postgres")
    await conn.execute("CREATE DATABASE migration_test")
    await conn.close()

    yield "postgresql://localhost/migration_test"

    conn = await asyncpg.connect("postgresql://localhost/postgres")
    await conn.execute("DROP DATABASE migration_test")
    await conn.close()

@pytest.mark.asyncio
async def test_all_migrations_apply(test_db):
    """Test that all migrations apply successfully."""
    runner = MigrationRunner(test_db)
    result = await runner.run()
    assert result["applied"] > 0

@pytest.mark.asyncio
async def test_all_migrations_rollback(test_db):
    """Test that all migrations can be rolled back."""
    # Apply all
    migrate_runner = MigrationRunner(test_db)
    await migrate_runner.run()

    # Rollback all
    rollback_runner = RollbackRunner(test_db)
    result = await rollback_runner.rollback_count(100)
    assert result["rolled_back"] > 0
```

## Production Deployment Checklist

Before running migrations in production:

- [ ] Backup database: `pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql`
- [ ] Test migration in staging environment
- [ ] Review migration SQL for performance impact
- [ ] Schedule maintenance window if needed
- [ ] Notify team of upcoming changes
- [ ] Have rollback plan ready
- [ ] Monitor database metrics during migration

After migration:

- [ ] Verify migration applied: `--status`
- [ ] Test application functionality
- [ ] Check for any performance degradation
- [ ] Update documentation if schema changed

## Getting Help

If you encounter issues not covered here:

1. Check PostgreSQL logs for detailed error messages
2. Review the migration SQL manually
3. Test in isolation with a fresh database
4. Contact the database team for assistance
