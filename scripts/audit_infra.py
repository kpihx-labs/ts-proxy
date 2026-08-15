import os
import sys
from pathlib import Path
from ts_proxy.config import ensure_secure_infra

# ANSI Colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
NC = "\033[0m"

def check_perm(path: Path, expected: str):
    if not path.exists():
        print(f"{YELLOW}SKIP{NC}  {path} (Not found)")
        return True
    
    current = oct(path.stat().st_mode & 0o777)
    if current == expected:
        print(f"{GREEN}PASS{NC}  {path} ({current})")
        return True
    else:
        print(f"{RED}FAIL{NC}  {path} (Expected {expected}, got {current})")
        return False

def audit():
    print(f"{CYAN}--- ts-proxy Infrastructure Audit ---{NC}")
    
    # Trigger application-level hardening
    ensure_secure_infra()
    
    data_dir = Path.home() / ".config" / "ts-proxy"
    tmp_dir = Path("/tmp/ts_proxy")
    
    all_passed = True
    
    # 1. Directories
    all_passed &= check_perm(data_dir, "0o700")
    all_passed &= check_perm(tmp_dir, "0o700")
    
    # 2. Files
    all_passed &= check_perm(data_dir / "secrets.json", "0o600")
    all_passed &= check_perm(data_dir / "config.yaml", "0o600")
    all_passed &= check_perm(data_dir / "proxy.log", "0o600")
    
    # 3. Security Invariants
    # Check if umask test works
    test_file = data_dir / ".audit_umask"
    try:
        with open(test_file, "w") as f:
            f.write("test")
        current_umask_mode = oct(test_file.stat().st_mode & 0o777)
        if current_umask_mode == "0o600":
            print(f"{GREEN}PASS{NC}  Umask Invariant (0o600)")
        else:
            print(f"{RED}FAIL{NC}  Umask Invariant (Got {current_umask_mode})")
            all_passed = False
        os.remove(test_file)
    except Exception as e:
        print(f"{RED}FAIL{NC}  Umask Test failed: {e}")
        all_passed = False

    if all_passed:
        print(f"\n{GREEN}✅ AUDIT PASSED{NC}")
        sys.exit(0)
    else:
        print(f"\n{RED}❌ AUDIT FAILED{NC}")
        sys.exit(1)

if __name__ == "__main__":
    audit()
