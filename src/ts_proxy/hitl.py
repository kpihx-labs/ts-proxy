import http.server
import json
import threading
import socketserver
import uuid

from .config import HITL_HOST, HITL_PORT, HITL_TIMEOUT_SECONDS

# Global state for HITL
HITL_RESULT = None
HITL_EVENT = threading.Event()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ts-proxy HITL Approval</title>
    <style>
        body {
            background-color: #0f172a;
            color: #f8fafc;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .glass-panel {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 40px;
            max-width: 600px;
            width: 100%;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }
        h2 { margin-top: 0; color: #facc15; }
        .payload {
            background: #1e293b;
            padding: 15px;
            border-radius: 8px;
            font-family: monospace;
            white-space: pre-wrap;
            color: #38bdf8;
            border: 1px solid rgba(255, 255, 255, 0.05);
            max-height: 400px;
            overflow-y: auto;
        }
        .buttons { display: flex; gap: 15px; margin-top: 30px; }
        button {
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-approve {
            background: #22c55e;
            color: #fff;
        }
        .btn-approve:hover { background: #16a34a; }
        .btn-reject {
            background: #ef4444;
            color: #fff;
        }
        .btn-reject:hover { background: #dc2626; }
    </style>
</head>
<body>
    <div class="glass-panel">
        <h2>⚠️ Action Approval Required</h2>
        <p><strong>Action:</strong> {action_name}</p>
        <p><strong>Payload / Target:</strong></p>
        <div class="payload">{payload_json}</div>
        <div class="buttons">
            <button class="btn-approve" onclick="submitDecision('approve')">APPROVE</button>
            <button class="btn-reject" onclick="submitDecision('reject')">REJECT</button>
        </div>
    </div>
    <script>
        function submitDecision(decision) {
            fetch('/submit?decision=' + decision, { method: 'POST' })
                .then(() => {
                    document.body.innerHTML = '<div class="glass-panel" style="text-align: center;"><h2>Response Received</h2><p>You can close this window.</p></div>';
                    setTimeout(() => window.close(), 1500);
                });
        }
    </script>
</body>
</html>
"""

HTML_EDITOR_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ts-proxy Config Editor</title>
    <style>
        body {
            background-color: #0f172a;
            color: #f8fafc;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .glass-panel {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 40px;
            max-width: 800px;
            width: 100%;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }
        h2 { margin-top: 0; color: #facc15; }
        textarea {
            background: #1e293b;
            padding: 15px;
            border-radius: 8px;
            font-family: monospace;
            color: #38bdf8;
            border: 1px solid rgba(255, 255, 255, 0.05);
            width: 100%;
            height: 400px;
            box-sizing: border-box;
            resize: vertical;
        }
        .buttons { display: flex; gap: 15px; margin-top: 30px; }
        button {
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-approve { background: #22c55e; color: #fff; }
        .btn-approve:hover { background: #16a34a; }
        .btn-reject { background: #ef4444; color: #fff; }
        .btn-reject:hover { background: #dc2626; }
    </style>
</head>
<body>
    <div class="glass-panel">
        <h2>ts-proxy Config Editor</h2>
        <textarea id="yamlEditor">{yaml_content}</textarea>
        <div class="buttons">
            <button class="btn-approve" onclick="saveConfig()">SAVE & APPLY</button>
            <button class="btn-reject" onclick="cancelEdit()">CANCEL</button>
        </div>
    </div>
    <script>
        function saveConfig() {
            const content = document.getElementById('yamlEditor').value;
            fetch('/submit-edit', {
                method: 'POST',
                headers: { 'Content-Type': 'text/plain' },
                body: content
            }).then(() => {
                document.body.innerHTML = '<div class="glass-panel" style="text-align: center;"><h2>Config Saved</h2><p>Validation will run in terminal. Close window.</p></div>';
                setTimeout(() => window.close(), 1500);
            });
        }
        function cancelEdit() {
            fetch('/submit-cancel', { method: 'POST' }).then(() => {
                document.body.innerHTML = '<div class="glass-panel" style="text-align: center;"><h2>Cancelled</h2><p>You can close this window.</p></div>';
                setTimeout(() => window.close(), 1500);
            });
        }
    </script>
</body>
</html>
"""


class HITLRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, action_name: str, payload: dict, tx_id: str, *args, **kwargs):
        self.action_name = action_name
        self.payload = payload
        self.tx_id = tx_id
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == f"/approve/{self.tx_id}":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            payload_str = json.dumps(self.payload, indent=2)
            html = HTML_TEMPLATE.replace("{action_name}", self.action_name).replace(
                "{payload_json}", payload_str
            )
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path.startswith("/submit?decision="):
            decision = self.path.split("=")[-1]
            global HITL_RESULT
            HITL_RESULT = decision == "approve"
            self.send_response(200)
            self.end_headers()
            global HITL_EVENT
            HITL_EVENT.set()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


class EditorRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, yaml_content: str, tx_id: str, *args, **kwargs):
        self.yaml_content = yaml_content
        self.tx_id = tx_id
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == f"/edit/{self.tx_id}":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            # Very basic escaping for textarea
            escaped = (
                self.yaml_content.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            html = HTML_EDITOR_TEMPLATE.replace("{yaml_content}", escaped)
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/submit-edit":
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len).decode("utf-8")
            global HITL_RESULT
            HITL_RESULT = post_body
            self.send_response(200)
            self.end_headers()
            global HITL_EVENT
            HITL_EVENT.set()
        elif self.path == "/submit-cancel":
            HITL_RESULT = None
            self.send_response(200)
            self.end_headers()
            HITL_EVENT.set()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def prompt_review(action_name: str, payload: dict) -> bool:
    """
    Spawns the local web server, prints the magic string to stdout, and blocks.
    Returns True if approved, False if rejected or timed out.
    """
    global HITL_RESULT, HITL_EVENT
    HITL_RESULT = None
    HITL_EVENT.clear()

    tx_id = str(uuid.uuid4())
    port = HITL_PORT
    host = HITL_HOST

    def handler(*args, **kwargs):
        return HITLRequestHandler(action_name, payload, tx_id, *args, **kwargs)

    try:
        httpd = socketserver.TCPServer((host, port), handler)
    except OSError:
        httpd = socketserver.TCPServer((host, 0), handler)
        port = httpd.server_address[1]

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    print(f"HITL_REQUIRED: http://127.0.0.1:{port}/approve/{tx_id}")

    hit = HITL_EVENT.wait(timeout=HITL_TIMEOUT_SECONDS)

    httpd.shutdown()
    httpd.server_close()

    if not hit:
        return False

    return HITL_RESULT


def prompt_config_edit(yaml_content: str) -> str | None:
    """
    Spawns the web editor. Returns the modified string if saved, or None if cancelled/timeout.
    """
    global HITL_RESULT, HITL_EVENT
    HITL_RESULT = None
    HITL_EVENT.clear()

    tx_id = str(uuid.uuid4())
    port = HITL_PORT
    host = HITL_HOST

    def handler(*args, **kwargs):
        return EditorRequestHandler(yaml_content, tx_id, *args, **kwargs)

    try:
        httpd = socketserver.TCPServer((host, port), handler)
    except OSError:
        httpd = socketserver.TCPServer((host, 0), handler)
        port = httpd.server_address[1]

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    print(f"HITL_REQUIRED: http://127.0.0.1:{port}/edit/{tx_id}")

    hit = HITL_EVENT.wait(timeout=HITL_TIMEOUT_SECONDS)

    httpd.shutdown()
    httpd.server_close()

    if not hit:
        return None

    return HITL_RESULT
