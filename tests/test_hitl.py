import re
from ts_proxy.hitl import HITLServer
from unittest.mock import MagicMock


def test_render_ui_default():
    mock_handler = MagicMock(spec=HITLServer)

    request_id = "test-123"
    req = {
        "func_name": "unknown_action",
        "payload": {"key": "value"},
        "rationale": "Testing rationale",
    }

    rendered = HITLServer._render_ui(mock_handler, request_id, req)

    assert "unknown_action" in rendered
    assert "Testing rationale" in rendered
    # Ensure data is injected
    assert "test-123" in rendered
    assert "value" in rendered


def test_render_ui_custom_template():
    mock_handler = MagicMock(spec=HITLServer)
    req = {
        "func_name": "update_acl",  # This should load the specific template
        "payload": {"hujson_payload": "// test"},
        "rationale": "Rationale",
    }

    rendered = HITLServer._render_ui(mock_handler, "id", req)
    assert "update_acl" in rendered
    assert "monaco-editor" in rendered  # Specific to the custom template


def test_data_injection_escaping():
    mock_handler = MagicMock(spec=HITLServer)
    req = {
        "func_name": "test",
        "payload": {"evil": "</script><script>alert(1)</script>"},
        "rationale": "Rationale",
    }
    rendered = HITLServer._render_ui(mock_handler, "id", req)

    # Check the hitl-data script content specifically
    data_match = re.search(
        r'<script id="hitl-data" type="application/json">(.*?)</script>',
        rendered,
        re.DOTALL,
    )
    assert data_match is not None
    data_content = data_match.group(1)
    assert "</script>" not in data_content
    assert "<\\/script>" in data_content


def test_render_ui_with_original_payload():
    mock_handler = MagicMock(spec=HITLServer)
    req = {
        "func_name": "update_acl",
        "payload": {"hujson_payload": "// modified"},
        "original_payload": {"acl_hujson": "// original"},
        "rationale": "Rationale",
    }
    rendered = HITLServer._render_ui(mock_handler, "id", req)
    assert "// original" in rendered
    assert "original_payload" in rendered
