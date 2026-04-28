#!/bin/bash
set -e

# ts-proxy Universal Uninstaller
# Part of KpihX-Labs Sovereign Infrastructure

CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}⌫ Uninstalling ts-proxy...${NC}"

# --- Paths ---
BIN_DIR="${HOME}/.local/bin"
SHIM_DEST="${BIN_DIR}/ts-proxy"
DATA_DIR="${HOME}/.ts-proxy"
TMP_DIR="/tmp/ts-proxy"

# --- Removal ---
if [ -L "${SHIM_DEST}" ]; then
    rm "${SHIM_DEST}"
    echo -e "✅ Removed host-side shim: ${SHIM_DEST}"
elif [ -f "${SHIM_DEST}" ]; then
    rm "${SHIM_DEST}"
    echo -e "✅ Removed binary: ${SHIM_DEST}"
else
    echo -e "ℹ️ Entrypoint not found in ${SHIM_DEST}"
fi

echo -e "🐳 Cleaning Docker resources..."
# Stop and remove any running containers for this image
docker ps -q --filter "ancestor=kpihx/ts-proxy:latest" | xargs -r docker rm -f &>/dev/null || true
# Remove the image
docker rmi kpihx/ts-proxy:latest 2>/dev/null || true

echo -e "🧹 Purging data and temporary files..."
rm -rf "${TMP_DIR}"
echo -e "✅ Purged temporary directory: ${TMP_DIR}"

# Mandatory purge for 100% cleanliness as requested
if [ -d "${DATA_DIR}" ]; then
    rm -rf "${DATA_DIR}"
    echo -e "✅ Purged data directory and secrets: ${DATA_DIR}"
fi

echo -e "\n${CYAN}✅ Total uninstallation complete. No debris left.${NC}"
