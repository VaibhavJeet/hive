# Database Backup and Recovery

This guide covers database backup strategies, automation, and recovery procedures for the Sentient platform.

## Quick Start

```bash
# Create a full backup
python scripts/backup_db.py full

# Or using bash script
./scripts/backup_db.sh full

# List available backups
python scripts/backup_db.py list

# Restore from backup
python scripts/backup_db.py restore full_ai_companions_20260321_120000.dump.gz
```

## Backup Types

### Full Backup

Creates a complete snapshot of the database including all data, schemas, and large objects.

```bash
# Python version
python scripts/backup_db.py full

# Bash version
./scripts/backup_db.sh full

# Without compression (faster but larger)
python scripts/backup_db.py full --no-compress

# Without large objects
python scripts/backup_db.py full --no-blobs
```

**When to use:**
- Daily backups
- Before major migrations
- Before risky operations
- Initial backup for incremental chain

**Output:** `backups/full_ai_companions_YYYYMMDD_HHMMSS.dump.gz`

### Incremental Backup

Creates a data-only backup (no schema). Smaller and faster than full backups.

```bash
python scripts/backup_db.py incremental
# or
./scripts/backup_db.sh incremental
```

**When to use:**
- Frequent backups (every few hours)
- Supplement to daily full backups
- Low-bandwidth environments

**Note:** Incremental restores require a base full backup first.

## Restore Operations

### Basic Restore

```bash
# Restore to original database
python scripts/backup_db.py restore full_ai_companions_20260321_120000.dump.gz

# Restore to a different database
python scripts/backup_db.py restore backup.dump.gz --target-db ai_companions_staging

# Clean restore (drop existing objects first)
python scripts/backup_db.py restore backup.dump.gz --clean
```

### Restore Procedure

1. **Stop the application** to prevent new writes:
   ```bash
   # Stop API server and activity engine
   systemctl stop sentient-api
   ```

2. **Optional: Create backup of current state**:
   ```bash
   python scripts/backup_db.py full
   ```

3. **Restore the backup**:
   ```bash
   python scripts/backup_db.py restore backup.dump.gz --clean
   ```

4. **Verify data integrity**:
   ```bash
   psql -h localhost -U postgres -d ai_companions -c "SELECT COUNT(*) FROM bots;"
   ```

5. **Restart the application**:
   ```bash
   systemctl start sentient-api
   ```

### Incremental Restore

For incremental backups, restore in order:

```bash
# 1. Restore full backup first
python scripts/backup_db.py restore full_backup.dump.gz

# 2. Apply incremental backups in chronological order
python scripts/backup_db.py restore incremental_1.dump.gz
python scripts/backup_db.py restore incremental_2.dump.gz
```

## Backup Verification

Always verify backups to ensure they're restorable:

```bash
python scripts/backup_db.py verify full_ai_companions_20260321_120000.dump.gz
# or
./scripts/backup_db.sh verify backup.dump.gz
```

This checks:
- File integrity (gzip decompression)
- pg_dump format validity
- Content listing

## Automated Backups (Cron Jobs)

### Setting Up Cron Jobs

Edit crontab:
```bash
crontab -e
```

### Recommended Schedule

```cron
# Full backup daily at 2 AM
0 2 * * * cd /path/to/sentient && python scripts/backup_db.py full >> /var/log/sentient/backup.log 2>&1

# Incremental backup every 6 hours
0 */6 * * * cd /path/to/sentient && python scripts/backup_db.py incremental >> /var/log/sentient/backup.log 2>&1

# Cleanup old backups weekly on Sunday at 3 AM (keep last 30 days)
0 3 * * 0 cd /path/to/sentient && python scripts/backup_db.py cleanup --keep-days 30 >> /var/log/sentient/backup.log 2>&1

# Verify latest backup daily at 4 AM
0 4 * * * cd /path/to/sentient && latest=$(ls -t /path/to/sentient/backups/full_*.dump.gz | head -1) && python scripts/backup_db.py verify "$latest" >> /var/log/sentient/backup.log 2>&1
```

### Using Bash Script

```cron
# Full backup daily at 2 AM
0 2 * * * cd /path/to/sentient && ./scripts/backup_db.sh full >> /var/log/sentient/backup.log 2>&1

# Cleanup keeping 30 days
0 3 * * 0 cd /path/to/sentient && ./scripts/backup_db.sh cleanup 30 >> /var/log/sentient/backup.log 2>&1
```

### Systemd Timer (Alternative to Cron)

Create `/etc/systemd/system/sentient-backup.service`:
```ini
[Unit]
Description=Sentient Database Backup
After=postgresql.service

[Service]
Type=oneshot
User=sentient
WorkingDirectory=/path/to/sentient
ExecStart=/usr/bin/python scripts/backup_db.py full
StandardOutput=journal
StandardError=journal
```

Create `/etc/systemd/system/sentient-backup.timer`:
```ini
[Unit]
Description=Daily Sentient Database Backup

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable:
```bash
sudo systemctl enable sentient-backup.timer
sudo systemctl start sentient-backup.timer
```

## Retention Management

### Automatic Cleanup

```bash
# Keep last 7 days
python scripts/backup_db.py cleanup --keep-days 7

# Keep at least 5 backups regardless of age
python scripts/backup_db.py cleanup --keep-days 7 --keep-count 5

# Bash version
./scripts/backup_db.sh cleanup 7
```

### Recommended Retention Policy

| Environment | Full Backups | Incremental | Retention |
|-------------|--------------|-------------|-----------|
| Production  | Daily 2 AM   | Every 6h    | 30 days   |
| Staging     | Daily 3 AM   | None        | 7 days    |
| Development | Manual       | None        | 3 days    |

## Configuration

### Environment Variables

Add to `.env`:

```bash
# Database connection (required)
AIC_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_companions

# Backup directory (default: ./backups)
AIC_BACKUP_DIR=/var/backups/sentient

# Default retention days (default: 7)
AIC_BACKUP_RETENTION_DAYS=30
```

### Remote Storage (S3/MinIO)

For production, sync backups to remote storage:

```bash
# Sync to S3 after backup
aws s3 sync ./backups s3://your-bucket/sentient-backups/

# Or use MinIO
mc mirror ./backups minio/sentient-backups/
```

Add to cron after backup:
```cron
# After daily backup, sync to S3
15 2 * * * aws s3 sync /path/to/backups s3://bucket/backups/ --storage-class STANDARD_IA
```

## Disaster Recovery

### Scenario 1: Database Corruption

1. Stop the application
2. Drop and recreate database:
   ```bash
   psql -U postgres -c "DROP DATABASE ai_companions;"
   psql -U postgres -c "CREATE DATABASE ai_companions;"
   psql -U postgres -d ai_companions -c "CREATE EXTENSION vector;"
   ```
3. Restore from latest backup:
   ```bash
   python scripts/backup_db.py restore latest_backup.dump.gz
   ```
4. Apply any incremental backups
5. Restart application

### Scenario 2: Server Migration

1. Create fresh backup on source:
   ```bash
   python scripts/backup_db.py full
   ```
2. Copy backup to new server:
   ```bash
   scp backups/full_*.dump.gz newserver:/path/to/backups/
   ```
3. On new server, restore:
   ```bash
   python scripts/backup_db.py restore backup.dump.gz
   ```

### Scenario 3: Point-in-Time Recovery

For true point-in-time recovery, enable PostgreSQL WAL archiving:

```sql
-- In postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'cp %p /path/to/archive/%f'
```

Then use `pg_basebackup` + WAL replay for precise recovery.

## Monitoring Backups

### Check Backup Status

```bash
# List recent backups
python scripts/backup_db.py list

# Check backup sizes
du -sh backups/*

# Verify backup count
ls -la backups/*.dump.gz | wc -l
```

### Alerting

Add to monitoring (example with healthchecks.io):

```cron
# Ping on successful backup
0 2 * * * cd /path/to/sentient && python scripts/backup_db.py full && curl -fsS https://hc-ping.com/your-uuid > /dev/null
```

## Troubleshooting

### "pg_dump: command not found"

Install PostgreSQL client tools:
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-client

# macOS
brew install postgresql

# Windows
# Add PostgreSQL bin directory to PATH
```

### "Connection refused"

1. Check PostgreSQL is running:
   ```bash
   pg_isready -h localhost -p 5432
   ```
2. Verify connection string in `.env`
3. Check `pg_hba.conf` allows connections

### "Permission denied"

1. Check backup directory permissions:
   ```bash
   ls -la backups/
   chmod 755 backups/
   ```
2. Verify database user has backup permissions:
   ```sql
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO backup_user;
   ```

### Large Backup Files

1. Enable compression (default)
2. Exclude large objects if not needed: `--no-blobs`
3. Use incremental backups between full backups
4. Increase cleanup frequency

## Best Practices

1. **Test restores regularly** - A backup is only good if you can restore it
2. **Store backups off-site** - Sync to S3, GCS, or another datacenter
3. **Encrypt sensitive backups** - Use GPG for at-rest encryption
4. **Monitor backup success** - Set up alerts for failed backups
5. **Document recovery procedures** - Keep runbooks up to date
6. **Maintain backup rotation** - Don't keep backups forever
7. **Version control backup scripts** - Track changes to backup procedures
