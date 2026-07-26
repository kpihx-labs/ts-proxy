import pytest
import json
import asyncio
import io
from unittest.mock import patch, MagicMock
from ts_proxy.hitl import (
    HITLServer,
    HITLResponse,
    request_approval,
    require_approval,
    request_text_edit,
)
from ts_proxy.exceptions import SecureProxyError


class MockRequest:
    def __init__(self, path, headers=None, rfile=None):
        self.path = path
        self.headers = headers or {}
        self.rfile = rfile or io.BytesIO()


def test_hitl_server_log_message():
    handler = MagicMock()
    HITLServer.log_message(handler, "test")  # Should do nothing


def test_hitl_server_get_review_not_found():
    handler = MagicMock(spec=HITLServer)
    handler.path = "/review?id=missing"
    HITLServer.active_requests = {}
    HITLServer.do_GET(handler)
    handler.send_error.assert_called_with(404, "Review request not found.")


def test_hitl_server_get_review_ok():
    handler = MagicMock()
    handler.path = "/review?id=123"
    handler.wfile = io.BytesIO()
    req = {
        "func_name": "test_func",
        "payload": {"a": 1},
        "loop": MagicMock(),
        "event": MagicMock(),
    }
    handler.active_requests = {"123": req}
    handler._render_ui.return_value = "<html></html>"
    HITLServer.active_requests = {"123": req}
    HITLServer.do_GET(handler)
    handler.send_response.assert_called_with(200)
    handler.send_header.assert_any_call("Content-type", "text/html")
    assert b"<html></html>" in handler.wfile.getvalue()


def test_hitl_server_post_submit_ok():
    handler = MagicMock()
    handler.path = "/submit"
    post_data_dict = {
        "id": "123",
        "status": "APPROVED",
        "payload": {"a": 2},
        "comment": "test",
    }
    post_data = json.dumps(post_data_dict)
    handler.headers = {"Content-Length": str(len(post_data))}
    handler.rfile = io.BytesIO(post_data.encode())
    handler.wfile = io.BytesIO()

    event = MagicMock()
    loop = MagicMock()
    req = {"loop": loop, "event": event, "payload": {"a": 1}}
    handler.active_requests = {"123": req}
    HITLServer.active_requests = {"123": req}

    HITLServer.do_POST(handler)
    assert req["result"].status == "APPROVED"
    assert req["result"].payload == {"a": 2}
    handler.send_response.assert_called_with(200)
    loop.call_soon_threadsafe.assert_called()


def test_hitl_server_post_not_found():
    handler = MagicMock()
    handler.path = "/submit"
    post_data = json.dumps({"id": "missing"})
    handler.headers = {"Content-Length": str(len(post_data))}
    handler.rfile = io.BytesIO(post_data.encode())
    HITLServer.active_requests = {}
    handler.active_requests = {}
    HITLServer.do_POST(handler)
    handler.send_error.assert_called_with(404)


def test_hitl_server_render_ui_error():
    handler = MagicMock()
    req = {"func_name": "missing", "payload": {}}
    with patch("pathlib.Path.exists", return_value=False):
        # Even default.html missing
        with patch("builtins.open", side_effect=Exception("Read error")):
            res = HITLServer._render_ui(handler, "123", req)
            assert "Critical Error" in res


@pytest.mark.asyncio
async def test_request_text_edit():
    with patch("ts_proxy.hitl.request_approval") as mock_req:
        mock_req.return_value = HITLResponse(status="APPROVED", payload="new text")
        res = await request_text_edit("test", "old text")
        assert res == "new text"

        mock_req.return_value = HITLResponse(status="REJECTED")
        res = await request_text_edit("test", "old text")
        assert res is None


@pytest.mark.asyncio
async def test_require_approval_rejected():
    class TestClient:
        @require_approval()
        async def my_action(self, payload, rationale=""):
            return "ok"

    client = TestClient()
    with patch("ts_proxy.hitl.request_approval") as mock_req:
        mock_req.return_value = HITLResponse(status="REJECTED", comment="No way")
        with pytest.raises(SecureProxyError) as exc:
            await client.my_action({"data": 1})
        assert "Rejected: No way" in str(exc.value)


@pytest.mark.asyncio
async def test_require_approval_approved():
    class TestClient:
        @require_approval()
        async def my_action(self, payload, rationale=""):
            return payload

    client = TestClient()
    with patch("ts_proxy.hitl.request_approval") as mock_req:
        mock_req.return_value = HITLResponse(status="APPROVED", payload={"data": 2})
        res = await client.my_action({"data": 1})
        assert res == {"data": 2}


def test_terminal_prompt_approve():
    req = {
        "func_name": "test_func",
        "payload": {"a": 1},
        "event": MagicMock(),
        "is_text": False,
    }
    with patch("builtins.input", side_effect=["a"]):
        from ts_proxy.hitl import _terminal_prompt

        _terminal_prompt("123", req)
        assert req["result"].status == "APPROVED"
        req["event"].set.assert_called()


def test_terminal_prompt_reject():
    req = {
        "func_name": "test_func",
        "payload": {"a": 1},
        "event": MagicMock(),
        "is_text": False,
    }
    with patch("builtins.input", side_effect=["r", "no reason"]):
        from ts_proxy.hitl import _terminal_prompt

        _terminal_prompt("123", req)
        assert req["result"].status == "REJECTED"
        assert req["result"].comment == "no reason"
        req["event"].set.assert_called()


def test_terminal_prompt_comment():
    req = {
        "func_name": "test_func",
        "payload": {"a": 1},
        "event": MagicMock(),
        "is_text": False,
        "comment_buffer": "",
    }
    with patch("builtins.input", side_effect=["c", "my comment", "a"]):
        from ts_proxy.hitl import _terminal_prompt

        _terminal_prompt("123", req)
        assert req["comment_buffer"] == "my comment"
        assert req["result"].status == "APPROVED"


def test_terminal_prompt_rationale():
    req = {
        "func_name": "test_func",
        "payload": {"a": 1},
        "event": MagicMock(),
        "is_text": False,
        "rationale": "my rationale",
    }
    with patch("builtins.input", side_effect=["a"]):
        from ts_proxy.hitl import _terminal_prompt

        _terminal_prompt("123", req)
        # Just check it doesn't crash, coverage will show it ran


def test_terminal_prompt_edit_json():
    req = {
        "func_name": "test_func",
        "payload": {"a": 1},
        "event": MagicMock(),
        "is_text": False,
    }
    with (
        patch("builtins.input", side_effect=["e", "a"]),
        patch("sys.stdin.read", return_value='{"a": 10}'),
    ):
        from ts_proxy.hitl import _terminal_prompt

        _terminal_prompt("123", req)
        assert req["payload"] == {"a": 10}


def test_terminal_prompt_edit_text():
    req = {
        "func_name": "test_func",
        "payload": "old text",
        "event": MagicMock(),
        "is_text": True,
    }
    with (
        patch("builtins.input", side_effect=["e", "a"]),
        patch("sys.stdin.read", return_value="new text"),
    ):
        from ts_proxy.hitl import _terminal_prompt

        _terminal_prompt("123", req)
        assert req["payload"] == "new text"


def test_terminal_prompt_edit_error():
    req = {
        "func_name": "test_func",
        "payload": {"a": 1},
        "event": MagicMock(),
        "is_text": False,
    }
    with (
        patch("builtins.input", side_effect=["e", "a"]),
        patch("sys.stdin.read", return_value="invalid json"),
    ):
        from ts_proxy.hitl import _terminal_prompt

        _terminal_prompt("123", req)
        # Should print error and continue, payload unchanged
        assert req["payload"] == {"a": 1}


@pytest.mark.asyncio
async def test_request_approval_full():
    with (
        patch("ts_proxy.hitl.HTTPServer") as mock_server_class,
        patch("ts_proxy.hitl.threading.Thread"),
        patch("ts_proxy.hitl.webbrowser.open", side_effect=Exception("Browser error")),
        patch("ts_proxy.hitl.sys.stdin.isatty", return_value=True),
    ):
        mock_server = mock_server_class.return_value

        # Simulate background task setting the event and comment_buffer
        async def set_event():
            await asyncio.sleep(0.1)
            if not HITLServer.active_requests:
                return
            request_id = list(HITLServer.active_requests.keys())[0]
            HITLServer.active_requests[request_id]["result"] = HITLResponse(
                status="APPROVED", payload={"ok": True}
            )
            HITLServer.active_requests[request_id]["comment_buffer"] = (
                "buffered comment"
            )
            HITLServer.active_requests[request_id]["event"].set()

        task = asyncio.create_task(set_event())

        res = await request_approval("test_func", {"input": 1}, rationale="test")
        await task
        assert res.status == "APPROVED"
        assert res.comment == "buffered comment"
        mock_server.server_close.assert_called()


@pytest.mark.asyncio
async def test_request_approval_port_retry():
    with (
        patch(
            "ts_proxy.hitl.HTTPServer", side_effect=[OSError("Port busy"), MagicMock()]
        ),
        patch("ts_proxy.hitl.threading.Thread"),
        patch("ts_proxy.hitl.webbrowser.open"),
        patch("ts_proxy.hitl.sys.stdin.isatty", return_value=False),
    ):
        # Simulate event set
        async def set_event():
            await asyncio.sleep(0.1)
            request_id = list(HITLServer.active_requests.keys())[0]
            HITLServer.active_requests[request_id]["result"] = HITLResponse(
                status="APPROVED"
            )
            HITLServer.active_requests[request_id]["event"].set()

        asyncio.create_task(set_event())
        res = await request_approval("test", {}, rationale="retry")
        assert res.status == "APPROVED"


@pytest.mark.asyncio
async def test_require_approval_no_payload_decorator():
    class TestClient:
        @require_approval()
        async def my_action(self):
            return "ok"

    client = TestClient()
    res = await client.my_action()
    assert res == "ok"


@pytest.mark.asyncio
async def test_require_approval_model_validation_kwargs():
    from ts_proxy.models import DeviceIDPayload

    class TestClient:
        @require_approval()
        async def my_action(self, payload: DeviceIDPayload, rationale=""):
            return payload

    client = TestClient()
    with patch("ts_proxy.hitl.request_approval") as mock_req:
        mock_req.return_value = HITLResponse(
            status="APPROVED", payload={"device_id": "new_id"}
        )
        res = await client.my_action(
            payload=DeviceIDPayload(device_id="old_id"), rationale="r"
        )
        assert res.device_id == "new_id"


@pytest.mark.asyncio
async def test_request_approval_no_rationale_error():
    with patch("ts_proxy.hitl.REQUIRED_RATIONALE", True):
        with pytest.raises(SecureProxyError) as exc:
            await request_approval("test_func", {}, rationale="")
        assert "Rationale is required" in str(exc.value)


def test_hitl_server_get_404():
    handler = MagicMock()
    handler.path = "/invalid"
    HITLServer.do_GET(handler)
    handler.send_error.assert_called_with(404)


@pytest.mark.asyncio
async def test_require_approval_model_validation():
    from ts_proxy.models import DeviceIDPayload

    class TestClient:
        @require_approval()
        async def my_action(self, payload: DeviceIDPayload, rationale=""):
            return payload

    client = TestClient()
    with patch("ts_proxy.hitl.request_approval") as mock_req:
        mock_req.return_value = HITLResponse(
            status="APPROVED", payload={"device_id": "new_id"}
        )
        res = await client.my_action(DeviceIDPayload(device_id="old_id"))
        assert res.device_id == "new_id"
        assert isinstance(res, DeviceIDPayload)


@pytest.mark.asyncio
async def test_require_approval_plain_dict_kwargs():
    class TestClient:
        @require_approval()
        async def my_action(self, payload: dict):
            return payload

    client = TestClient()
    with patch("ts_proxy.hitl.request_approval") as mock_req:
        mock_req.return_value = HITLResponse(status="APPROVED", payload={"new": 1})
        res = await client.my_action(payload={"old": 1})
        assert res == {"new": 1}


@pytest.mark.asyncio
async def test_require_approval_plain_dict_args():
    class TestClient:
        @require_approval()
        async def my_action(self, payload: dict):
            return payload

    client = TestClient()
    with patch("ts_proxy.hitl.request_approval") as mock_req:
        mock_req.return_value = HITLResponse(status="APPROVED", payload={"new": 2})
        res = await client.my_action({"old": 2})
        assert res == {"new": 2}
