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
DEFAULT_DATA_DIR = "/root/.ts_proxy" # Inside container
HOST_DATA_DIR = Path.home() / ".ts_proxy"

def _pick_host_port() -> int:
    with socket.socket(socket.socket.AF_INET, socket.SOCK_STREAM) as s:
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
    cmd.extend(["-v", f"{HOST_DATA_DIR}:/root/.ts_proxy"])

    # Mount /tmp/ts_proxy for autosaves
    host_tmp = Path("/tmp/ts_proxy")
    host_tmp.mkdir(parents=True, exist_ok=True)
    cmd.extend(["-v", f"{host_tmp}:/tmp/ts_proxy"])

    cmd.append(DEFAULT_IMAGE)
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
            
            sys.stdout.write(line)
            sys.stdout.flush()

    thread = threading.Thread(target=intercept_stdout, daemon=True)
    thread.start()
    
    returncode = process.wait()
    sys.exit(returncode)

if __name__ == "__main__":
    run_shim(sys.argv[1:])
