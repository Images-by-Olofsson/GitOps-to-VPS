#!/bin/bash
# rollback.sh - Rollback to previous deployment
# Called by GitHub Actions if health-check fails
# Usage: ./rollback.sh <deploy_path>

set -euo pipefail

DEPLOY_PATH="${1:?Error: Deploy path required}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${DEPLOY_PATH}/docker-compose.yml.backup"
LOG_FILE="${DEPLOY_PATH}/deploy.log"

echo "========================================="
echo "  ROLLBACK STARTED: ${TIMESTAMP}"
echo "========================================="

# --- 1. Check backup exists ---
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "[✗] No backup file found at ${BACKUP_FILE}"
    echo "[✗] Cannot rollback - manual intervention required!"
    echo "${TIMESTAMP} | ROLLBACK | FAILED (no backup)" >> "${LOG_FILE}"
    exit 1
fi

# --- 2. Restore backup ---
echo "[→] Restoring backup..."
cp "${BACKUP_FILE}" "${DEPLOY_PATH}/docker-compose.yml"
echo "[✓] docker-compose.yml restored from backup"

# --- 3. Redeploy with old config ---
echo "[→] Restarting containers with previous config..."
cd "${DEPLOY_PATH}"
docker compose up -d --remove-orphans 2>&1 || {
    echo "[✗] Rollback deploy failed! Manual intervention required."
    echo "${TIMESTAMP} | ROLLBACK | FAILED (compose up)" >> "${LOG_FILE}"
    exit 1
}

# --- 4. Log rollback ---
echo "${TIMESTAMP} | ROLLBACK | SUCCESS" >> "${LOG_FILE}"
echo ""
echo "========================================="
echo "  ROLLBACK COMPLETE: $(date +%H:%M:%S)"
echo "  Previous version restored."
echo "========================================="
