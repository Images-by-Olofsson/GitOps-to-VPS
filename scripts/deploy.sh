#!/bin/bash
# deploy.sh - Deploy script for VPS
# Called by GitHub Actions after validation passes
# Usage: ./deploy.sh <deploy_path>

set -euo pipefail

DEPLOY_PATH="${1:?Error: Deploy path required}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${DEPLOY_PATH}/docker-compose.yml.backup"
LOG_FILE="${DEPLOY_PATH}/deploy.log"

echo "========================================="
echo "  DEPLOY STARTED: ${TIMESTAMP}"
echo "========================================="

# --- 1. Backup current state ---
if [ -f "${DEPLOY_PATH}/docker-compose.yml" ]; then
    cp "${DEPLOY_PATH}/docker-compose.yml" "${BACKUP_FILE}"
    echo "[✓] Backup created: docker-compose.yml.backup"
else
    echo "[!] No existing docker-compose.yml to backup (first deploy?)"
fi

# --- 2. Pull & Deploy Core Infrastructure ---
echo "[→] Starting Core Infrastructure Deploy..."
if [ -d "${DEPLOY_PATH}/infrastructure" ]; then
    cd "${DEPLOY_PATH}/infrastructure"
    
    # Generate .env for infrastructure
    printf "CF_API_EMAIL=%s\nCF_DNS_API_TOKEN=%s\n" "${CF_API_EMAIL:-}" "${CF_DNS_API_TOKEN:-}" > .env

    docker compose pull 2>&1 || echo "[!] Infrastructure pull warning"
    docker compose up -d --remove-orphans 2>&1 || {
        echo "[✗] Infrastructure deploy failed!"
        exit 1
    }
    echo "[✓] Core Infrastructure running!"
    cd "${DEPLOY_PATH}"
fi

# --- 3. Pull & Deploy Applications ---
echo "[→] Starting Application Deploy..."
cd "${DEPLOY_PATH}"
docker compose pull 2>&1 || {
    echo "[✗] Application pull failed!"
    exit 1
}
echo "[✓] Applications pulled successfully"

docker compose up -d --remove-orphans 2>&1 || {
    echo "[✗] Application deploy failed!"
    exit 1
}
echo "[✓] Applications started"

# --- 4. Pull & Deploy Additional Apps ---
echo "[→] Starting Additional Apps Deploy..."
if [ -d "${DEPLOY_PATH}/apps" ]; then
    for app_dir in "${DEPLOY_PATH}/apps"/*/; do
        if [ -d "$app_dir" ] && [ -f "${app_dir}docker-compose.yml" ]; then
            app_name=$(basename "$app_dir")
            echo "   Deploying $app_name..."
            cd "$app_dir"
            
            # Generate .env for each app with all available secrets
            # This ensures variables like ${GF_ADMIN_PASSWORD} are resolved
            printf "CF_API_EMAIL=%s\nCF_DNS_API_TOKEN=%s\nGF_ADMIN_PASSWORD=%s\nOPNSENSE_HOST=%s\nOPNSENSE_API_KEY=%s\nOPNSENSE_API_SECRET=%s\nTS_AUTHKEY=%s\n" \
                "${CF_API_EMAIL:-}" "${CF_DNS_API_TOKEN:-}" "${GF_ADMIN_PASSWORD:-}" \
                "${OPNSENSE_HOST:-}" "${OPNSENSE_API_KEY:-}" "${OPNSENSE_API_SECRET:-}" \
                "${TS_AUTHKEY:-}" > .env

            docker compose pull 2>&1 || echo "   [!] $app_name pull warning"
            docker compose up -d --remove-orphans 2>&1 || {
                echo "   [✗] $app_name deploy failed!"
                exit 1
            }
            echo "   [✓] $app_name started"
        fi
    done
fi

# --- 5. Log deploy ---
echo "${TIMESTAMP} | DEPLOY | SUCCESS" >> "${LOG_FILE}"
echo ""
echo "========================================="
echo "  DEPLOY COMPLETE: $(date +%H:%M:%S)"
echo "========================================="
