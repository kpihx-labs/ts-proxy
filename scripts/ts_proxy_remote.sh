#!/bin/bash
set -e

# Sovereign ts-proxy Remote Wrapper
# Part of KpihX-Labs Infrastructure

# --- Configuration & Defaults ---
DEFAULT_HOST="homelab"
DEFAULT_PORT="1143"
SSH_CTRL_DIR="${HOME}/.ssh/control"

# --- Branding ---
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

function usage() {
    echo "Usage: ts-proxy [WRAPPER_OPTIONS] [COMMANDS]"
    echo ""
    echo "Wrapper Options:"
    echo "  --host, -H HOST    Remote host (default: ${DEFAULT_HOST})"
    echo "  --port, -P PORT    Port for SSH Tunnel (default: ${DEFAULT_PORT})"
    echo "  --close            Close existing SSH master connection"
    echo "  --help, -h         Show this help"
    echo ""
    echo "Example:"
    echo "  ts-proxy do list-users"
    echo "  ts-proxy -H server-01 -P 8080 do list-users"
    exit 1
}

# --- Parsing ---
REMOTE_HOST="${TS_PROXY_HOST:-$DEFAULT_HOST}"
TUNNEL_PORT="${TS_PROXY_PORT:-$DEFAULT_PORT}"
REMOTE_ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --host|-H) REMOTE_HOST="$2"; shift 2 ;;
        --port|-P) TUNNEL_PORT="$2"; shift 2 ;;
        --close)
            CTRL_PATH="${SSH_CTRL_DIR}/ts-proxy-remote"
            if [ -S "${CTRL_PATH}" ]; then
                ssh -S "${CTRL_PATH}" -O exit "${REMOTE_HOST}" 2>/dev/null || true
                echo "✅ Tunnel closed."
            fi
            exit 0
            ;;
        --help|-h) usage ;;
        *) REMOTE_ARGS+=("$1"); shift ;;
    esac
done

if [ ${#REMOTE_ARGS[@]} -eq 0 ]; then
    usage
fi

# --- Optimization: ControlMaster ---
mkdir -p "${SSH_CTRL_DIR}"
# Use a predictable control path for this host
CTRL_PATH="${SSH_CTRL_DIR}/ts-proxy-${REMOTE_HOST}"

# Check/Start Master Connection & Tunnel
if ! ssh -S "${CTRL_PATH}" -O check "${REMOTE_HOST}" 2>/dev/null; then
    echo -e "${CYAN}🚀 Initializing optimized SSH tunnel to ${REMOTE_HOST}...${NC}"
    # -M: Master mode
    # -f: Background
    # -N: No remote command
    # -L: Local forward (Port-forwarding for HITL)
    # -o ExitOnForwardFailure=yes: Ensure we get the port
    ssh -M -f -N -S "${CTRL_PATH}" \
        -L "${TUNNEL_PORT}:localhost:${TUNNEL_PORT}" \
        -o ExitOnForwardFailure=yes \
        -o ControlPersist=10m \
        "${REMOTE_HOST}"
fi

# --- Execution ---
# We use the master connection (-S) for near-instant execution
# We forward TS_PROXY_PORT so the remote shim uses the same port as our tunnel
ssh -S "${CTRL_PATH}" -t "${REMOTE_HOST}" \
    "TS_PROXY_PORT=${TUNNEL_PORT} ts-proxy ${REMOTE_ARGS[*]}"
