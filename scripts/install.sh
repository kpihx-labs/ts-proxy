#!/bin/bash
set -e

# ts-proxy Universal Installer (Release Mode)
# Part of KpihX-Labs Sovereign Infrastructure

# --- Configuration ---
GITHUB_RAW_URL="https://raw.githubusercontent.com/KpihX/ts-proxy/main"
DOCKER_IMAGE="kpihx/ts-proxy:latest"

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
BIN_DIR="${HOME}/.local/bin"
DATA_DIR="${HOME}/.ts_proxy"
SHIM_DEST="${BIN_DIR}/ts-proxy"

# --- Setup ---
echo -e "🛠️ Setting up directories..."
mkdir -p "${BIN_DIR}"
mkdir -p "${DATA_DIR}"

# --- Image Deployment ---
if [ -f "Dockerfile" ]; then
    echo -e "🐳 Local repository detected. Building appliance..."
    docker build -t "${DOCKER_IMAGE}" .
else
    echo -e "🚀 Release mode detected. Pulling appliance image..."
    # Note: If this is a private registry, 'docker login' must be performed beforehand.
    docker pull "${DOCKER_IMAGE}"
fi

# --- Shim Deployment ---
if [ -f "scripts/ts_proxy_shim.py" ]; then
    echo -e "🔗 Linking host-side shim from local source..."
    chmod +x "scripts/ts_proxy_shim.py"
    ln -sf "$(pwd)/scripts/ts_proxy_shim.py" "${SHIM_DEST}"
else
    echo -e "📥 Downloading host-side shim from GitHub..."
    curl -sSL "${GITHUB_RAW_URL}/scripts/ts_proxy_shim.py" -o "${SHIM_DEST}"
    chmod +x "${SHIM_DEST}"
fi

# --- Finalize ---
echo -e "\n${GREEN}✅ ts-proxy installed successfully!${NC}"
echo -e "🚀 You can now use '${CYAN}ts-proxy do --help${NC}' to explore."
echo -e "📂 Config, logs and secrets live in: ${YELLOW}${DATA_DIR}${NC}"

# Check if BIN_DIR is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "\n${YELLOW}⚠️ Warning: ${BIN_DIR} is not in your PATH.${NC}"
    echo -e "Please add it to your shell config (e.g., ~/.bashrc or ~/.zshrc):"
    echo -e "  export PATH=\"\$PATH:${BIN_DIR}\""
fi
