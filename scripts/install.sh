#!/bin/bash
set -e

# ts-proxy Universal Installer
# Part of KpihX-Labs Sovereign Infrastructure

# --- Colors & Branding ---
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
echo "    ╔╦╗┌─┐  ╔═╗╦═╗╔═╗═╗ ╦╦ ╦"
echo "     ║ └─┐  ╠═╝╠╦╝║ ║╔╩╦╝╚╦╝"
echo "     ╩ └─┘  ╩  ╩╚═╚═╝╩ ╚═ ╩ "
echo "   Sovereign Tailscale Proxy"
echo -e "${NC}"

# --- Prerequisites ---
echo -e "🔍 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Error: docker is not installed.${NC}"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: python3 is required for the host-side shim.${NC}"
    exit 1
fi

# --- Paths ---
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${HOME}/.local/bin"
DATA_DIR="${HOME}/.ts-proxy"
SHIM_SRC="${INSTALL_DIR}/scripts/ts_proxy_shim.py"
SHIM_DEST="${BIN_DIR}/ts-proxy"

# --- Setup ---
echo -e "🛠️ Setting up directories..."
mkdir -p "${BIN_DIR}"
mkdir -p "${DATA_DIR}"

echo -e "🐳 Building Sovereign Appliance (Docker)..."
cd "${INSTALL_DIR}"
docker build -t kpihx/ts-proxy:latest .

echo -e "🔗 Installing host-side shim..."
chmod +x "${SHIM_SRC}"
ln -sf "${SHIM_SRC}" "${SHIM_DEST}"

# --- Finalize ---
echo -e "\n${GREEN}✅ ts-proxy installed successfully!${NC}"
echo -e "🚀 You can now use '${CYAN}ts-proxy do --help${NC}' to explore."
echo -e "📂 Config and secrets live in: ${YELLOW}${DATA_DIR}${NC}"

# Check if BIN_DIR is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "\n${YELLOW}⚠️ Warning: ${BIN_DIR} is not in your PATH.${NC}"
    echo -e "Please add it to your shell config (e.g., ~/.bashrc or ~/.zshrc):"
    echo -e "  export PATH=\"\$PATH:${BIN_DIR}\""
fi
