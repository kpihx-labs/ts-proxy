from pathlib import Path
import os
import asyncio
import json
import sys
import uuid
import webbrowser
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional, Callable, Coroutine
from functools import wraps

from .exceptions import SecureProxyError
from .config import (
    HITL_MAX_RETRIES,
    REQUIRED_RATIONALE,
    get_hitl_port,
    HITL_HOST as CONFIG_HOST,
)

# --- ANSI Colors for TUI ---
CYAN = "\033[0;36m"
YELLOW = "\033[1;33m"
GREEN = "\033[0;32m"
RED = "\033[0;31m"
BOLD = "\033[1m"
NC = "\033[0m"


@dataclass
class HITLResponse:
    status: str  # "APPROVED", "REJECTED", "ADJUSTED"
    payload: Optional[Any] = None
    comment: str = ""


class HITLServer(BaseHTTPRequestHandler):
    """Centralized HITL UI Server with Glassmorphism design."""

    active_requests: Dict[str, Dict[str, Any]] = {}

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/review"):
            query = self.path.split("?")[-1]
            request_id = query.split("id=")[-1]

            if request_id not in self.active_requests:
                self.send_error(404, "Review request not found.")
                return

            req = self.active_requests[request_id]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(self._render_ui(request_id, req).encode("utf-8"))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/submit":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(post_data)

            request_id = data.get("id")
            if request_id in self.active_requests:
                status = data.get("status")
                payload = data.get("payload")
                req = self.active_requests[request_id]

                print(
                    f"{GREEN}✓ HITL Submission received: {status} for {request_id}{NC}"
                )

                req["result"] = HITLResponse(
                    status=status, payload=payload, comment=data.get("comment", "")
                )

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))

                # Thread-safe event set
                loop = req["loop"]
                loop.call_soon_threadsafe(req["event"].set)
            else:
                print(f"{RED}❌ HITL Error: request_id {request_id} not found{NC}")
                self.send_error(404)

    def _render_ui(self, request_id: str, req: Dict[str, Any]) -> str:
        """Renders the UI using specific or default template."""
        func_name = req["func_name"]

        # Determine template to use
        template_dir = Path(__file__).parent / "template"
        template_path = template_dir / f"{func_name}.html"
        if not template_path.exists():
            template_path = template_dir / "default.html"

        try:
            with open(template_path, "r") as f:
                template = f.read()
        except Exception as e:
            return f"<html><body>Critical Error: Template {template_path.name} not found or unreadable: {e}</body></html>"

        # Safe data injection via JSON blob
        client_data = {
            "id": request_id,
            "func_name": func_name,
            "rationale": req.get("rationale", ""),
            "payload": req["payload"],
            "original_payload": req.get("original_payload"),
            "is_text": req.get("is_text", False),
        }

        data_json = json.dumps(client_data).replace("</script>", "<\\/script>")

        # Simple template substitution
        replacements = {
            "{{HITL_DATA_JSON}}": data_json,
            "{{FUNC_NAME}}": func_name,
            "{{RATIONALE}}": req.get("rationale", ""),
        }

        rendered = template
        for key, val in replacements.items():
            rendered = rendered.replace(key, str(val))

        return rendered


def _terminal_prompt(request_id: str, req: Dict[str, Any]):
    """TUI Fallback for terminal-based approval."""
    print(f"\n{YELLOW}{BOLD}⚠️  HITL TERMINAL FALLBACK ACTIVE{NC}")
    print(f"{CYAN}Function:{NC} {req['func_name']}")
    if req.get("rationale"):
        print(f"{CYAN}Rationale:{NC} {req['rationale']}")
    payload_display = (
        req["payload"] if req.get("is_text") else json.dumps(req["payload"], indent=2)
    )
    print(f"{CYAN}Content:{NC}\n{payload_display}")

    while True:
        choice = (
            input(f"\n{BOLD}[A]pprove | [R]eject | [E]dit | [C]omment ? {NC}")
            .strip()
            .lower()
        )

        if choice == "a":
            req["result"] = HITLResponse(status="APPROVED", payload=req["payload"])
            req["event"].set()
            break
        elif choice == "r":
            comment = input(f"{RED}Reason for rejection? {NC}").strip()
            req["result"] = HITLResponse(status="REJECTED", comment=comment)
            req["event"].set()
            break
        elif choice == "c":
            comment = input(f"{YELLOW}Your comment? {NC}").strip()
            print(f"{GREEN}✓ Comment attached. Please Approve or Reject now.{NC}")
            req["comment_buffer"] = comment
        elif choice == "e":
            print(
                f"{YELLOW}Paste the new content below (Press Ctrl+D when finished):{NC}"
            )
            try:
                new_str = sys.stdin.read()
                if not req.get("is_text"):
                    req["payload"] = json.loads(new_str)
                else:
                    req["payload"] = new_str
                print(f"{GREEN}✓ Content updated.{NC}")
            except Exception as e:
                print(f"{RED}❌ Invalid input: {e}{NC}")


async def request_text_edit(
    name: str,
    initial_text: str,
    rationale: str = "",
    original_text: Optional[str] = None,
) -> Optional[str]:
    """Trigger a web UI for bulk text editing (e.g. config)."""
    response = await request_approval(
        name,
        initial_text,
        is_text=True,
        rationale=rationale,
        original_payload=original_text,
    )
    if response.status == "APPROVED":
        return response.payload
    return None


async def request_approval(
    func_name: str,
    payload: Any,
    is_text: bool = False,
    rationale: str = "",
    original_payload: Optional[Any] = None,
) -> HITLResponse:
    if REQUIRED_RATIONALE and not rationale:
        raise SecureProxyError(f"Rationale is required for action: {func_name}")

    request_id = str(uuid.uuid4())
    event = asyncio.Event()
    loop = asyncio.get_running_loop()

    req_context = {
        "func_name": func_name,
        "payload": payload,
        "original_payload": original_payload,
        "is_text": is_text,
        "rationale": rationale,
        "event": event,
        "loop": loop,
        "result": None,
        "comment_buffer": "",
    }
    HITLServer.active_requests[request_id] = req_context

    host = CONFIG_HOST
    port = get_hitl_port()

    server = None
    max_retries = HITL_MAX_RETRIES
    for i in range(max_retries):
        try:
            server = HTTPServer((host, port + i), HITLServer)
            port = port + i
            break
        except OSError as e:
            if i == max_retries - 1:
                raise SecureProxyError(f"Failed to start HITL server: {e}")
            continue

    url = f"http://{host}:{port}/review?id={request_id}"
    print(f"\n{BOLD}🚀 [HITL] ACTION REVIEW REQUIRED{NC}")
    print(f"🔗 BROWSER: {url}")

    if os.environ.get("SSH_CLIENT") or os.environ.get("SSH_TTY"):
        print(f"{YELLOW}💡 SSH Detected: Ensure you have a tunnel active:{NC}")
        print(f"   ssh -L {port}:localhost:{port} [your-host]")

    print(f"HITL_REQUIRED: {url}")

    try:

        def serve_until_done():
            while not event.is_set():
                server.handle_request()

        http_thread = threading.Thread(target=serve_until_done, daemon=True)
        http_thread.start()

        webbrowser.open(url)
    except Exception:
        pass

    if sys.stdin.isatty():
        tui_thread = threading.Thread(
            target=_terminal_prompt, args=(request_id, req_context), daemon=True
        )
        tui_thread.start()

    await event.wait()

    response = req_context["result"]
    if req_context["comment_buffer"] and not response.comment:
        response.comment = req_context["comment_buffer"]

    del HITLServer.active_requests[request_id]
    server.server_close()

    return response


def require_approval():
    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            payload_obj = kwargs.get("payload") or (args[0] if args else None)
            if not payload_obj:
                return await func(self, *args, **kwargs)

            payload_dict = (
                payload_obj.model_dump()
                if hasattr(payload_obj, "model_dump")
                else payload_obj
            )

            # Extract rationale and original_payload from kwargs if present
            rationale = kwargs.get("rationale", "")
            original_payload = kwargs.get("original_payload")

            response = await request_approval(
                func.__name__,
                payload_dict,
                rationale=rationale,
                original_payload=original_payload,
            )

            if response.status == "REJECTED":
                raise SecureProxyError(
                    f"Rejected: {response.comment}"
                    if response.comment
                    else "Action rejected."
                )

            # If APPROVED or ADJUSTED (both return APPROVED status in this refined logic)
            if response.payload:
                if hasattr(payload_obj, "model_validate"):
                    new_payload = payload_obj.__class__.model_validate(response.payload)
                    if kwargs.get("payload"):
                        kwargs["payload"] = new_payload
                    else:
                        args = (new_payload,) + args[1:]
                else:
                    if kwargs.get("payload"):
                        kwargs["payload"] = response.payload
                    else:
                        args = (response.payload,) + args[1:]

            return await func(self, *args, **kwargs)

        return wrapper

    return decorator
