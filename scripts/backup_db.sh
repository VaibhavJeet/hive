#!/bin/bash
#
# Database Backup Script for Sentient Platform
#
# Supports:
# - Full backups (pg_dump)
# - Incremental backups (data-only dumps)
# - Restore operations
# - Compression (gzip)
# - Retention management
#
# Usage:
#   ./scripts/backup_db.sh full                      # Full backup
#   ./scripts/backup_db.sh incremental               # Incremental backup
#   ./scripts/backup_db.sh restore <backup_file>     # Restore from backup
#   ./scripts/backup_db.sh list                      # List available backups
#   ./scripts/backup_db.sh cleanup [days]            # Keep only last N days (default: 7)
#   ./scripts/backup_db.sh verify <backup_file>      # Verify backup integrity
#

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# Configuration with defaults
DB_URL="${AIC_DATABASE_URL:-postgresql+asyncpg://postgres:postgres@localhost:5432/ai_companions}"
BACKUP_DIR="${AIC_BACKUP_DIR:-$PROJECT_DIR/backups}"
RETENTION_DAYS="${AIC_BACKUP_RETENTION_DAYS:-7}"

# Parse database URL (remove asyncpg driver prefix)
DB_URL="${DB_URL/postgresql+asyncpg:\/\//postgresql:\/\/}"

# Extract components from URL
parse_db_url() {
    # Format: postgresql://user:pass@host:port/database
    local url="$1"
    url="${url#postgresql://}"

    # Extract user:pass
    local userpass="${url%%@*}"
    DB_USER="${userpass%%:*}"
    DB_PASS="${userpass#*:}"

    # Extract host:port/database
    local hostportdb="${url#*@}"
    local hostport="${hostportdb%%/*}"
    DB_NAME="${hostportdb#*/}"

    DB_HOST="${hostport%%:*}"
    DB_PORT="${hostport#*:}"

    # Defaults
    DB_HOST="${DB_HOST:-localhost}"
    DB_PORT="${DB_PORT:-5432}"
    DB_USER="${DB_USER:-postgres}"
    DB_PASS="${DB_PASS:-postgres}"
    DB_NAME="${DB_NAME:-ai_companions}"
}

parse_db_url "$DB_URL"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Full backup
full_backup() {
    local compress="${1:-true}"
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_name="full_${DB_NAME}_${timestamp}"
    local backup_file="$BACKUP_DIR/${backup_name}.dump"

    log_info "Creating full backup: $backup_file"

    PGPASSWORD="$DB_PASS" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --format=custom \
        --verbose \
        --blobs \
        -f "$backup_file"

    if [[ "$compress" == "true" ]]; then
        log_info "Compressing backup..."
        gzip "$backup_file"
        backup_file="${backup_file}.gz"
    fi

    # Create metadata file
    local meta_file="${backup_file}.meta"
    cat > "$meta_file" << EOF
type=full
database=$DB_NAME
timestamp=$timestamp
compressed=$compress
size=$(stat -c%s "$backup_file" 2>/dev/null || stat -f%z "$backup_file")
EOF

    local size_mb
    size_mb=$(echo "scale=2; $(stat -c%s "$backup_file" 2>/dev/null || stat -f%z "$backup_file") / 1048576" | bc)

    log_info "Backup complete: $backup_file"
    log_info "Size: ${size_mb} MB"

    echo "$backup_file"
}

# Incremental backup (data-only)
incremental_backup() {
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_name="incremental_${DB_NAME}_${timestamp}"
    local backup_file="$BACKUP_DIR/${backup_name}.dump"

    log_info "Creating incremental backup: $backup_file"

    PGPASSWORD="$DB_PASS" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --format=custom \
        --data-only \
        --verbose \
        -f "$backup_file"

    log_info "Compressing backup..."
    gzip "$backup_file"
    backup_file="${backup_file}.gz"

    # Create metadata file
    local meta_file="${backup_file}.meta"
    cat > "$meta_file" << EOF
type=incremental
database=$DB_NAME
timestamp=$timestamp
compressed=true
size=$(stat -c%s "$backup_file" 2>/dev/null || stat -f%z "$backup_file")
EOF

    local size_mb
    size_mb=$(echo "scale=2; $(stat -c%s "$backup_file" 2>/dev/null || stat -f%z "$backup_file") / 1048576" | bc)

    log_info "Incremental backup complete: $backup_file"
    log_info "Size: ${size_mb} MB"

    echo "$backup_file"
}

# Restore from backup
restore_backup() {
    local backup_file="$1"
    local target_db="${2:-$DB_NAME}"
    local clean="${3:-false}"

    # Check if file exists
    if [[ ! -f "$backup_file" ]]; then
        # Try in backup directory
        backup_file="$BACKUP_DIR/$backup_file"
        if [[ ! -f "$backup_file" ]]; then
            log_error "Backup file not found: $1"
            exit 1
        fi
    fi

    local restore_file="$backup_file"

    # Decompress if needed
    if [[ "$backup_file" == *.gz ]]; then
        log_info "Decompressing backup..."
        restore_file="${backup_file%.gz}"
        gunzip -c "$backup_file" > "$restore_file"
        trap "rm -f '$restore_file'" EXIT
    fi

    log_info "Restoring backup to database: $target_db"
    log_warn "This may take a while for large databases..."

    local clean_flag=""
    if [[ "$clean" == "true" ]]; then
        clean_flag="--clean"
    fi

    PGPASSWORD="$DB_PASS" pg_restore \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$target_db" \
        --verbose \
        --no-owner \
        --no-privileges \
        $clean_flag \
        "$restore_file" || true  # pg_restore may return non-zero for warnings

    log_info "Restore complete!"
}

# List backups
list_backups() {
    echo ""
    printf "%-12s %-20s %-16s %-10s %s\n" "Type" "Database" "Timestamp" "Size (MB)" "File"
    echo "--------------------------------------------------------------------------------"

    for meta_file in $(ls -t "$BACKUP_DIR"/*.meta 2>/dev/null); do
        local backup_file="${meta_file%.meta}"

        if [[ ! -f "$backup_file" ]]; then
            continue
        fi

        local type=$(grep "^type=" "$meta_file" | cut -d= -f2)
        local database=$(grep "^database=" "$meta_file" | cut -d= -f2)
        local timestamp=$(grep "^timestamp=" "$meta_file" | cut -d= -f2)
        local size_bytes=$(stat -c%s "$backup_file" 2>/dev/null || stat -f%z "$backup_file")
        local size_mb=$(echo "scale=2; $size_bytes / 1048576" | bc)
        local filename=$(basename "$backup_file")

        printf "%-12s %-20s %-16s %-10s %s\n" "$type" "$database" "$timestamp" "$size_mb" "$filename"
    done
}

# Cleanup old backups
cleanup_backups() {
    local keep_days="${1:-$RETENTION_DAYS}"
    local removed=0

    log_info "Cleaning up backups older than $keep_days days..."

    # Find and remove old backups
    for backup_file in "$BACKUP_DIR"/*.dump* ; do
        [[ ! -f "$backup_file" ]] && continue
        [[ "$backup_file" == *.meta ]] && continue

        # Check file age
        local file_age_days
        if [[ "$(uname)" == "Darwin" ]]; then
            # macOS
            file_age_days=$(( ($(date +%s) - $(stat -f%m "$backup_file")) / 86400 ))
        else
            # Linux
            file_age_days=$(( ($(date +%s) - $(stat -c%Y "$backup_file")) / 86400 ))
        fi

        if [[ $file_age_days -gt $keep_days ]]; then
            log_info "Removing old backup: $(basename "$backup_file")"
            rm -f "$backup_file"
            rm -f "${backup_file}.meta"
            ((removed++))
        fi
    done

    log_info "Removed $removed old backup(s)"
}

# Verify backup
verify_backup() {
    local backup_file="$1"

    # Check if file exists
    if [[ ! -f "$backup_file" ]]; then
        backup_file="$BACKUP_DIR/$backup_file"
        if [[ ! -f "$backup_file" ]]; then
            log_error "Backup file not found: $1"
            exit 1
        fi
    fi

    local verify_file="$backup_file"

    # Decompress if needed
    if [[ "$backup_file" == *.gz ]]; then
        log_info "Decompressing for verification..."
        verify_file="${backup_file%.gz}.verify_tmp"
        if ! gunzip -c "$backup_file" > "$verify_file"; then
            log_error "Decompression failed!"
            rm -f "$verify_file"
            exit 1
        fi
        trap "rm -f '$verify_file'" EXIT
    fi

    log_info "Verifying backup integrity..."

    if pg_restore --list "$verify_file" > /dev/null 2>&1; then
        local item_count
        item_count=$(pg_restore --list "$verify_file" | wc -l)
        log_info "Backup verification successful!"
        log_info "Contents: $item_count items"
        exit 0
    else
        log_error "Backup verification failed!"
        exit 1
    fi
}

# Show usage
usage() {
    cat << EOF
Database Backup Script for Sentient Platform

Usage: $0 <command> [options]

Commands:
    full                      Create a full database backup
    incremental               Create an incremental (data-only) backup
    restore <file>            Restore from a backup file
    list                      List available backups
    cleanup [days]            Remove backups older than N days (default: 7)
    verify <file>             Verify backup file integrity

Options for restore:
    --target-db <name>        Target database name (default: same as source)
    --clean                   Drop existing objects before restore

Examples:
    $0 full                                 # Full backup
    $0 incremental                          # Incremental backup
    $0 list                                 # List all backups
    $0 restore backup.dump.gz               # Restore backup
    $0 restore backup.dump.gz --clean       # Clean restore
    $0 verify backup.dump.gz                # Verify backup
    $0 cleanup 30                           # Keep last 30 days

Cron job examples (add with: crontab -e):
    # Full backup daily at 2 AM
    0 2 * * * cd $PROJECT_DIR && ./scripts/backup_db.sh full >> /var/log/db_backup.log 2>&1

    # Incremental backup every 6 hours
    0 */6 * * * cd $PROJECT_DIR && ./scripts/backup_db.sh incremental >> /var/log/db_backup.log 2>&1

    # Cleanup weekly on Sunday at 3 AM
    0 3 * * 0 cd $PROJECT_DIR && ./scripts/backup_db.sh cleanup 30 >> /var/log/db_backup.log 2>&1

Environment Variables:
    AIC_DATABASE_URL          Database connection string
    AIC_BACKUP_DIR            Backup directory (default: ./backups)
    AIC_BACKUP_RETENTION_DAYS Default retention days (default: 7)
EOF
}

# Main
main() {
    local command="${1:-}"

    case "$command" in
        full)
            full_backup
            ;;
        incremental)
            incremental_backup
            ;;
        restore)
            shift
            local backup_file="${1:-}"
            local target_db=""
            local clean="false"

            shift || true
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --target-db)
                        target_db="$2"
                        shift 2
                        ;;
                    --clean)
                        clean="true"
                        shift
                        ;;
                    *)
                        shift
                        ;;
                esac
            done

            if [[ -z "$backup_file" ]]; then
                log_error "Backup file required"
                usage
                exit 1
            fi

            restore_backup "$backup_file" "${target_db:-$DB_NAME}" "$clean"
            ;;
        list)
            list_backups
            ;;
        cleanup)
            cleanup_backups "${2:-$RETENTION_DAYS}"
            ;;
        verify)
            if [[ -z "${2:-}" ]]; then
                log_error "Backup file required"
                usage
                exit 1
            fi
            verify_backup "$2"
            ;;
        -h|--help|help)
            usage
            ;;
        *)
            log_error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

main "$@"
