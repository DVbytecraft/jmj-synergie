#!/usr/bin/env bash
# =============================================================================
#  JMJ Synergie — Script de backup PostgreSQL
#
#  Usage :
#    ./scripts/backup.sh              # backup manuel
#    ./scripts/backup.sh restore <fichier.sql.gz>   # restauration
#
#  Cron (exemple — tous les jours à 02h00) :
#    0 2 * * * /opt/jmj-synergie/scripts/backup.sh >> /var/log/jmj-backup.log 2>&1
# =============================================================================

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────

CONTAINER="jmj_postgres"
DB_NAME="${POSTGRES_DB:-jmj_synergie}"
DB_USER="${POSTGRES_USER:-jmj_admin}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/jmj_${DB_NAME}_${TIMESTAMP}.sql.gz"

# ─── Fonctions ────────────────────────────────────────────────────────────────

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
error(){ echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2; exit 1; }

require_env() {
    [[ -z "${POSTGRES_PASSWORD:-}" ]] && error "POSTGRES_PASSWORD non défini. Sourcez votre .env avant d'exécuter ce script."
}

backup() {
    require_env
    mkdir -p "$BACKUP_DIR"

    log "Démarrage backup → $BACKUP_FILE"

    docker exec "$CONTAINER" \
        pg_dump \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            --no-password \
            --format=plain \
            --no-owner \
            --no-acl \
        | gzip -9 > "$BACKUP_FILE"

    local size
    size=$(du -sh "$BACKUP_FILE" | cut -f1)
    log "Backup terminé — taille : $size"

    # Nettoyage des anciens backups
    local deleted
    deleted=$(find "$BACKUP_DIR" -name "jmj_${DB_NAME}_*.sql.gz" \
        -mtime +"$RETENTION_DAYS" -print -delete | wc -l | tr -d ' ')
    [[ "$deleted" -gt 0 ]] && log "Nettoyage : $deleted fichier(s) supprimé(s) (>$RETENTION_DAYS jours)"

    log "Backup OK : $BACKUP_FILE"
}

restore() {
    local file="${1:-}"
    [[ -z "$file" ]] && error "Précisez le fichier à restaurer : $0 restore <fichier.sql.gz>"
    [[ ! -f "$file" ]] && error "Fichier introuvable : $file"

    require_env

    log "ATTENTION : la restauration va écraser la base '$DB_NAME'."
    read -rp "Confirmer ? (oui/non) : " confirm
    [[ "$confirm" != "oui" ]] && { log "Restauration annulée."; exit 0; }

    log "Restauration depuis $file …"

    # Terminer les connexions actives
    docker exec "$CONTAINER" psql \
        -U "$DB_USER" \
        -d postgres \
        -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid();" \
        > /dev/null

    # Recréer la base
    docker exec "$CONTAINER" psql \
        -U "$DB_USER" \
        -d postgres \
        -c "DROP DATABASE IF EXISTS $DB_NAME; CREATE DATABASE $DB_NAME OWNER $DB_USER;" \
        > /dev/null

    # Restaurer
    gunzip -c "$file" | docker exec -i "$CONTAINER" \
        psql -U "$DB_USER" -d "$DB_NAME" -q

    log "Restauration terminée."
}

verify() {
    require_env
    local latest
    latest=$(find "$BACKUP_DIR" -name "jmj_${DB_NAME}_*.sql.gz" \
        -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)

    [[ -z "$latest" ]] && error "Aucun backup trouvé dans $BACKUP_DIR"

    log "Vérification du dernier backup : $latest"

    # Vérifier l'intégrité gzip
    gunzip -t "$latest" && log "Intégrité gzip : OK" || error "Fichier corrompu !"

    # Lister les tables dans le dump (vérification basique du contenu)
    local table_count
    table_count=$(gunzip -c "$latest" | grep -c "^CREATE TABLE" || true)
    log "Tables trouvées dans le dump : $table_count"

    local age_hours
    age_hours=$(( ( $(date +%s) - $(stat -c %Y "$latest" 2>/dev/null || stat -f %m "$latest") ) / 3600 ))
    [[ "$age_hours" -gt 26 ]] && log "AVERTISSEMENT : dernier backup vieux de ${age_hours}h (>26h)"

    log "Vérification OK"
}

# ─── Point d'entrée ───────────────────────────────────────────────────────────

case "${1:-backup}" in
    backup)  backup ;;
    restore) restore "${2:-}" ;;
    verify)  verify ;;
    *) echo "Usage: $0 {backup|restore <fichier>|verify}" >&2; exit 1 ;;
esac
