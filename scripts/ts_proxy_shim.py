#!/usr/bin/env python3
import os
import sys
import subprocess
import socket
import threading
import shutil
from pathlib import Path

# --- Configuration ---
DEFAULT_IMAGE = "kpihx/ts-proxy:latest"
DEFAULT_DATA_DIR = "/home/tsuser/.ts_proxy" # Inside container (Non-Root)
HOST_DATA_DIR = Path.home() / ".ts_proxy"

# --- Colors ---
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
NC = "\033[0m"

def _pick_host_port() -> int:
    # Favor environment variable (passed by remote wrapper)
    env_port = os.environ.get("TS_PROXY_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass

    # Try default port 1143
    default_port = 1143
    with socket.socket(socket.socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("", default_port))
            return default_port
        except OSError:
            # Fallback to random if 1143 is taken
            s.bind(("", 0))
            return s.getsockname()[1]

def _build_docker_command(args: list[str], port: int) -> list[str]:
    workspace = Path.cwd()
    cmd = [
        "docker", "run", "--rm", "-i",
        "-e", "PYTHONUNBUFFERED=1",
        "-e", f"HITL_PORT={port}",
        "-e", "HITL_HOST=0.0.0.0",
        "-v", f"{workspace}:/app",
        "-w", "/app",
        "-p", f"127.0.0.1:{port}:{port}",
        "--user", f"{os.getuid()}:{os.getgid()}",
    ]
    
    if sys.stdin.isatty():
        cmd.append("-t")

    # Mount secrets if they exist (Sovereign Prod Mount)
    secret_path = Path("/var/run/secrets/ts-auth.json")
    if secret_path.exists():
        cmd.extend(["-v", f"{secret_path}:/var/run/secrets/ts-auth.json:ro"])
    elif (workspace / "secrets" / "ts-auth.json").exists():
        cmd.extend(["-v", f"{workspace}/secrets/ts-auth.json:/var/run/secrets/ts-auth.json:ro"])

    # Mount data dir for persistence (secrets.json, config.yaml, logs)
    HOST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(HOST_DATA_DIR, 0o700)
    cmd.extend(["-v", f"{HOST_DATA_DIR}:{DEFAULT_DATA_DIR}"])

    # Mount /tmp/ts_proxy for autosaves
    host_tmp = Path("/tmp/ts_proxy")
    host_tmp.mkdir(parents=True, exist_ok=True)
    os.chmod(host_tmp, 0o700)
    cmd.extend(["-v", f"{host_tmp}:/tmp/ts_proxy"])

    cmd.append(DEFAULT_IMAGE)
    # Forward the host-mapped port to the containerized CLI
    cmd.extend(["--port", str(port)])
    cmd.extend(args)
    return cmd

def run_shim(args: list[str]):
    port = _pick_host_port()
    cmd = _build_docker_command(args, port)
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    def intercept_stdout():
        for line in process.stdout:
            if "HITL_REQUIRED:" in line:
                url = line.split("HITL_REQUIRED:")[1].strip()
                print(f"🚀 [Host] Intercepted HITL request. Opening: {url}")
                try:
                    if shutil.which("xdg-open"):
                        subprocess.run(["xdg-open", url], check=False)
                    elif sys.platform == "darwin":
                        subprocess.run(["open", url], check=False)
                except Exception as e:
                    print(f"⚠️ [Host] Failed to open browser: {e}")
            
            if "UPGRADE_REQUIRED:" in line:
                print(f"\n{CYAN}🐳 [Host] Sovereign Upgrade triggered. Pulling latest image...{NC}")
                subprocess.run(["docker", "pull", DEFAULT_IMAGE], check=False)
                print(f"{GREEN}✅ [Host] Image {DEFAULT_IMAGE} updated successfully.{NC}\n")

            sys.stdout.write(line)
            sys.stdout.flush()

    thread = threading.Thread(target=intercept_stdout, daemon=True)
    thread.start()
    
    returncode = process.wait()
    sys.exit(returncode)

if __name__ == "__main__":
    run_shim(sys.argv[1:])
