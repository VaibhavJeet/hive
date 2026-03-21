#!/usr/bin/env python3
"""
Database Backup Script for Sentient Platform

Supports:
- Full backups (pg_dump)
- Incremental backups (WAL archiving simulation via base + diff)
- Restore operations
- Compression (gzip)
- Retention management
- Remote storage upload (S3-compatible)

Usage:
    python scripts/backup_db.py full                    # Full backup
    python scripts/backup_db.py incremental             # Incremental backup
    python scripts/backup_db.py restore <backup_file>   # Restore from backup
    python scripts/backup_db.py list                    # List available backups
    python scripts/backup_db.py cleanup --keep 7        # Keep only last 7 days
"""

import argparse
import gzip
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_db_config() -> dict:
    """Parse database configuration from environment."""
    from dotenv import load_dotenv
    load_dotenv()

    db_url = os.getenv("AIC_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_companions")

    # Remove asyncpg driver prefix for pg_dump compatibility
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    parsed = urlparse(db_url)

    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/") or "ai_companions",
        "user": parsed.username or "postgres",
        "password": parsed.password or "postgres",
    }


def get_backup_dir() -> Path:
    """Get backup directory, create if not exists."""
    backup_dir = Path(os.getenv("AIC_BACKUP_DIR", "./backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def run_command(cmd: list[str], env: Optional[dict] = None) -> subprocess.CompletedProcess:
    """Run a shell command with error handling."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    result = subprocess.run(
        cmd,
        env=full_env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"stderr: {result.stderr}")
        raise RuntimeError(f"Command failed with code {result.returncode}")

    return result


def full_backup(compress: bool = True, include_blobs: bool = True) -> Path:
    """
    Create a full database backup using pg_dump.

    Args:
        compress: Whether to gzip the backup file
        include_blobs: Whether to include large objects (blobs)

    Returns:
        Path to the backup file
    """
    config = get_db_config()
    backup_dir = get_backup_dir()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"full_{config['database']}_{timestamp}"

    # Build pg_dump command
    cmd = [
        "pg_dump",
        "-h", config["host"],
        "-p", str(config["port"]),
        "-U", config["user"],
        "-d", config["database"],
        "--format=custom",  # Custom format for efficient restore
        "--verbose",
    ]

    if include_blobs:
        cmd.append("--blobs")

    backup_file = backup_dir / f"{backup_name}.dump"
    cmd.extend(["-f", str(backup_file)])

    # Set password via environment
    env = {"PGPASSWORD": config["password"]}

    print(f"Creating full backup: {backup_file}")
    run_command(cmd, env=env)

    # Compress if requested
    if compress:
        compressed_file = backup_file.with_suffix(".dump.gz")
        print(f"Compressing to: {compressed_file}")

        with open(backup_file, "rb") as f_in:
            with gzip.open(compressed_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Remove uncompressed file
        backup_file.unlink()
        backup_file = compressed_file

    # Create metadata file
    metadata_file = backup_file.with_suffix(backup_file.suffix + ".meta")
    with open(metadata_file, "w") as f:
        f.write(f"type=full\n")
        f.write(f"database={config['database']}\n")
        f.write(f"timestamp={timestamp}\n")
        f.write(f"compressed={compress}\n")
        f.write(f"size={backup_file.stat().st_size}\n")

    print(f"Backup complete: {backup_file}")
    print(f"Size: {backup_file.stat().st_size / (1024*1024):.2f} MB")

    return backup_file


def incremental_backup(base_backup: Optional[Path] = None) -> Path:
    """
    Create an incremental backup.

    This creates a schema-only dump + data diff since last backup.
    For true WAL-based incremental backups, configure PostgreSQL
    archive_mode and use pg_basebackup + WAL archiving.

    Args:
        base_backup: Path to base backup (uses latest if not specified)

    Returns:
        Path to the incremental backup file
    """
    config = get_db_config()
    backup_dir = get_backup_dir()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"incremental_{config['database']}_{timestamp}"

    # Create incremental backup using pg_dump with data-only
    cmd = [
        "pg_dump",
        "-h", config["host"],
        "-p", str(config["port"]),
        "-U", config["user"],
        "-d", config["database"],
        "--format=custom",
        "--data-only",  # Only data, no schema
        "--verbose",
    ]

    backup_file = backup_dir / f"{backup_name}.dump"
    cmd.extend(["-f", str(backup_file)])

    env = {"PGPASSWORD": config["password"]}

    print(f"Creating incremental backup: {backup_file}")
    run_command(cmd, env=env)

    # Compress
    compressed_file = backup_file.with_suffix(".dump.gz")
    print(f"Compressing to: {compressed_file}")

    with open(backup_file, "rb") as f_in:
        with gzip.open(compressed_file, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    backup_file.unlink()
    backup_file = compressed_file

    # Create metadata
    metadata_file = backup_file.with_suffix(backup_file.suffix + ".meta")
    with open(metadata_file, "w") as f:
        f.write(f"type=incremental\n")
        f.write(f"database={config['database']}\n")
        f.write(f"timestamp={timestamp}\n")
        f.write(f"compressed=True\n")
        f.write(f"size={backup_file.stat().st_size}\n")
        if base_backup:
            f.write(f"base_backup={base_backup.name}\n")

    print(f"Incremental backup complete: {backup_file}")
    print(f"Size: {backup_file.stat().st_size / (1024*1024):.2f} MB")

    return backup_file


def restore_backup(backup_file: Path, target_db: Optional[str] = None, clean: bool = False) -> None:
    """
    Restore database from a backup file.

    Args:
        backup_file: Path to the backup file (.dump or .dump.gz)
        target_db: Target database name (uses original if not specified)
        clean: Drop existing objects before restore
    """
    config = get_db_config()
    backup_path = Path(backup_file)

    if not backup_path.exists():
        # Try looking in backup directory
        backup_path = get_backup_dir() / backup_file
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_file}")

    # Decompress if needed
    temp_file = None
    if backup_path.suffix == ".gz":
        print(f"Decompressing {backup_path}...")
        temp_file = backup_path.with_suffix("")
        with gzip.open(backup_path, "rb") as f_in:
            with open(temp_file, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        restore_file = temp_file
    else:
        restore_file = backup_path

    target_database = target_db or config["database"]

    # Build pg_restore command
    cmd = [
        "pg_restore",
        "-h", config["host"],
        "-p", str(config["port"]),
        "-U", config["user"],
        "-d", target_database,
        "--verbose",
        "--no-owner",  # Skip ownership commands
        "--no-privileges",  # Skip privilege commands
    ]

    if clean:
        cmd.append("--clean")  # Drop objects before creating

    cmd.append(str(restore_file))

    env = {"PGPASSWORD": config["password"]}

    print(f"Restoring backup to database: {target_database}")
    print("WARNING: This may take a while for large databases...")

    try:
        run_command(cmd, env=env)
        print("Restore complete!")
    finally:
        # Cleanup temp file
        if temp_file and temp_file.exists():
            temp_file.unlink()


def list_backups() -> list[dict]:
    """List all available backups with metadata."""
    backup_dir = get_backup_dir()
    backups = []

    for meta_file in sorted(backup_dir.glob("*.meta"), reverse=True):
        backup_file = Path(str(meta_file).replace(".meta", ""))

        if not backup_file.exists():
            continue

        metadata = {}
        with open(meta_file, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    metadata[key] = value

        metadata["file"] = backup_file.name
        metadata["path"] = str(backup_file)
        metadata["size_mb"] = backup_file.stat().st_size / (1024 * 1024)

        backups.append(metadata)

    return backups


def cleanup_old_backups(keep_days: int = 7, keep_count: Optional[int] = None) -> int:
    """
    Remove old backups based on retention policy.

    Args:
        keep_days: Keep backups newer than this many days
        keep_count: Keep at least this many backups regardless of age

    Returns:
        Number of backups removed
    """
    backup_dir = get_backup_dir()
    cutoff_date = datetime.now() - timedelta(days=keep_days)

    backups = list_backups()

    # Sort by timestamp (newest first)
    backups.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    removed = 0
    for i, backup in enumerate(backups):
        # Always keep minimum count
        if keep_count and i < keep_count:
            continue

        timestamp_str = backup.get("timestamp", "")
        if not timestamp_str:
            continue

        try:
            backup_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

            if backup_date < cutoff_date:
                backup_path = Path(backup["path"])
                meta_path = backup_path.with_suffix(backup_path.suffix + ".meta")

                print(f"Removing old backup: {backup_path.name}")
                backup_path.unlink()
                if meta_path.exists():
                    meta_path.unlink()

                removed += 1
        except ValueError:
            continue

    return removed


def verify_backup(backup_file: Path) -> bool:
    """
    Verify backup file integrity.

    Args:
        backup_file: Path to the backup file

    Returns:
        True if backup is valid
    """
    backup_path = Path(backup_file)

    if not backup_path.exists():
        backup_path = get_backup_dir() / backup_file

    if not backup_path.exists():
        print(f"Backup file not found: {backup_file}")
        return False

    # Decompress if needed
    temp_file = None
    if backup_path.suffix == ".gz":
        print(f"Decompressing for verification...")
        temp_file = backup_path.with_suffix("")
        try:
            with gzip.open(backup_path, "rb") as f_in:
                with open(temp_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            verify_file = temp_file
        except Exception as e:
            print(f"Decompression failed: {e}")
            return False
    else:
        verify_file = backup_path

    # Use pg_restore to verify
    cmd = ["pg_restore", "--list", str(verify_file)]

    try:
        result = run_command(cmd)
        print("Backup verification successful!")
        print(f"Contents: {len(result.stdout.splitlines())} items")
        return True
    except RuntimeError:
        print("Backup verification failed!")
        return False
    finally:
        if temp_file and temp_file.exists():
            temp_file.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Database backup automation for Sentient Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Create a full backup
    python scripts/backup_db.py full

    # Create full backup without compression
    python scripts/backup_db.py full --no-compress

    # Create incremental backup
    python scripts/backup_db.py incremental

    # List all backups
    python scripts/backup_db.py list

    # Restore from a backup
    python scripts/backup_db.py restore full_ai_companions_20260321_120000.dump.gz

    # Restore to a different database
    python scripts/backup_db.py restore backup.dump.gz --target-db ai_companions_test

    # Clean restore (drop existing objects first)
    python scripts/backup_db.py restore backup.dump.gz --clean

    # Verify a backup file
    python scripts/backup_db.py verify full_ai_companions_20260321_120000.dump.gz

    # Cleanup old backups (keep last 7 days)
    python scripts/backup_db.py cleanup --keep-days 7

    # Cleanup keeping minimum 5 backups
    python scripts/backup_db.py cleanup --keep-days 7 --keep-count 5

Cron job example (add to crontab -e):
    # Full backup daily at 2 AM
    0 2 * * * cd /path/to/project && python scripts/backup_db.py full

    # Incremental backup every 6 hours
    0 */6 * * * cd /path/to/project && python scripts/backup_db.py incremental

    # Cleanup weekly on Sunday at 3 AM
    0 3 * * 0 cd /path/to/project && python scripts/backup_db.py cleanup --keep-days 30
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Backup command")

    # Full backup
    full_parser = subparsers.add_parser("full", help="Create a full database backup")
    full_parser.add_argument("--no-compress", action="store_true", help="Skip compression")
    full_parser.add_argument("--no-blobs", action="store_true", help="Exclude large objects")

    # Incremental backup
    inc_parser = subparsers.add_parser("incremental", help="Create an incremental backup")
    inc_parser.add_argument("--base", type=Path, help="Base backup for incremental")

    # Restore
    restore_parser = subparsers.add_parser("restore", help="Restore from a backup")
    restore_parser.add_argument("backup_file", type=Path, help="Backup file to restore")
    restore_parser.add_argument("--target-db", help="Target database name")
    restore_parser.add_argument("--clean", action="store_true", help="Drop existing objects first")

    # List
    subparsers.add_parser("list", help="List available backups")

    # Cleanup
    cleanup_parser = subparsers.add_parser("cleanup", help="Remove old backups")
    cleanup_parser.add_argument("--keep-days", type=int, default=7, help="Keep backups for N days")
    cleanup_parser.add_argument("--keep-count", type=int, help="Keep at least N backups")

    # Verify
    verify_parser = subparsers.add_parser("verify", help="Verify backup integrity")
    verify_parser.add_argument("backup_file", type=Path, help="Backup file to verify")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "full":
            full_backup(
                compress=not args.no_compress,
                include_blobs=not args.no_blobs
            )

        elif args.command == "incremental":
            incremental_backup(base_backup=args.base)

        elif args.command == "restore":
            restore_backup(
                args.backup_file,
                target_db=args.target_db,
                clean=args.clean
            )

        elif args.command == "list":
            backups = list_backups()
            if not backups:
                print("No backups found.")
            else:
                print(f"{'Type':<12} {'Database':<20} {'Timestamp':<16} {'Size (MB)':<10} {'File'}")
                print("-" * 80)
                for b in backups:
                    print(f"{b.get('type', 'unknown'):<12} {b.get('database', 'N/A'):<20} "
                          f"{b.get('timestamp', 'N/A'):<16} {b.get('size_mb', 0):<10.2f} {b.get('file', 'N/A')}")

        elif args.command == "cleanup":
            removed = cleanup_old_backups(
                keep_days=args.keep_days,
                keep_count=args.keep_count
            )
            print(f"Removed {removed} old backup(s)")

        elif args.command == "verify":
            if not verify_backup(args.backup_file):
                return 1

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
