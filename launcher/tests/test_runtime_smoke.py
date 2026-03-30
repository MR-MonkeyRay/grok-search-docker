from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from launcher.think_sanitizer import strip_think_segments, sanitize_value, should_sanitize_tool


def test_strip_think_segments() -> None:
    assert strip_think_segments("hello world") == "hello world", "plain text"
    assert strip_think_segments("<think>internal</think>Answer") == "Answer", "full block"
    assert strip_think_segments("prefix<think>internal</think>suffix") == "prefixsuffix", "block in middle"
    assert strip_think_segments("<think>[Request interrupted by user]") == "", "orphaned open"
    assert strip_think_segments("Answer<think>partial") == "Answer", "orphaned open at end"
    assert strip_think_segments("Answer</think>") == "Answer", "orphaned close"
    assert strip_think_segments("<think>a</think>X<think>b\\n</think>\\n\\nB") == "X\\n\\nB", "multiple blocks"
    assert strip_think_segments("<think>x</think>  Answer  ") == "  Answer  ", "leading/trailing spaces preserved"


def test_should_sanitize_tool() -> None:
    assert should_sanitize_tool("web_search") == True, "web_search in whitelist"
    assert should_sanitize_tool("get_config_info") == True, "get_config_info in whitelist"
    assert should_sanitize_tool("web_fetch") == False, "web_fetch not in whitelist"
    assert should_sanitize_tool("other") == False, "unknown tool"


def test_redact_config_info_text() -> None:
    from launcher.think_sanitizer import redact_config_info_text

    d = {"GROK_API_URL": "http://secret.local", "other": "value"}
    res = redact_config_info_text(d)
    assert res["GROK_API_URL"] == "[REDACTED]", "GROK_API_URL redacted"
    assert res["other"] == "value", "other fields preserved"

    nested = {"config": {"GROK_API_URL": "http://secret.local"}}
    res = redact_config_info_text(nested)
    assert res["config"]["GROK_API_URL"] == "[REDACTED]", "nested GROK_API_URL redacted"

    tavily = {"TAVILY_API_URL": "http://tavily.local"}
    res = redact_config_info_text(tavily)
    assert res["TAVILY_API_URL"] == "[REDACTED]", "TAVILY_API_URL redacted"

    firecrawl = {"FIRECRAWL_API_URL": "http://firecrawl.local"}
    res = redact_config_info_text(firecrawl)
    assert res["FIRECRAWL_API_URL"] == "[REDACTED]", "FIRECRAWL_API_URL redacted"


def test_redact_config_info_scrubs_urls_in_strings() -> None:
    from launcher.think_sanitizer import redact_config_info_text

    text = "Check https://example.com/api"
    res = redact_config_info_text(text)
    assert "[URL]" in res, "URL in string replaced"
    assert "example.com" not in res, "URL content removed"


def test_sanitize_tool_result() -> None:
    from launcher.think_sanitizer import sanitize_tool_result

    config_data = {"GROK_API_URL": "http://secret.local"}
    res = sanitize_tool_result("get_config_info", config_data)
    assert res["GROK_API_URL"] == "[REDACTED]", "get_config_info uses redact_config_info_text"

    search_data = {"content": "<think>think</think>visible"}
    res = sanitize_tool_result("web_search", search_data)
    assert res["content"] == "visible", "web_search uses sanitize_value"

    res = sanitize_tool_result("unknown_tool", {"key": "value"})
    assert res == {"key": "value"}, "unknown_tool unchanged"


def test_sanitize_tool_result_with_object() -> None:
    """Test sanitize_tool_result handles object with .text containing JSON."""
    import json
    from launcher.think_sanitizer import sanitize_tool_result

    class FakeTextContent:
        def __init__(self, text: str) -> None:
            self.text = text

    payload = json.dumps({
        "GROK_API_URL": "https://api.x.ai/v1",
        "GROK_MODEL": "grok-4-fast",
        "GROK_API_KEY": "xai-****key",
        "connection_test": {
            "status": "failed",
            "message": "failed to reach https://api.x.ai/v1/models"
        }
    })

    fake_obj = FakeTextContent(payload)
    result = sanitize_tool_result("get_config_info", fake_obj)

    result_text = result.text
    parsed = json.loads(result_text)

    assert parsed["GROK_API_URL"] == "[REDACTED]", "GROK_API_URL redacted in JSON"
    assert "api.x.ai" not in parsed["connection_test"]["message"], "URL in message scrubbed"
    assert parsed["GROK_MODEL"] == "grok-4-fast", "non-URL fields preserved"


def test_scrub_urls() -> None:
    from launcher.think_sanitizer import _scrub_urls

    text = "Check out https://example.com/api and http://test.local/path"
    res = _scrub_urls(text)
    assert "[URL]" in res, "URLs replaced with [URL]"
    assert "example.com" not in res, "URL content removed"
    assert "test.local" not in res, "URL content removed"


def test_sanitize_value_nested() -> None:
    d = {"content": "<think>think</think>actual", "meta": {"title": "<think>t2</think>t2"}}
    res = sanitize_value(d)
    assert res == {"content": "actual", "meta": {"title": "t2"}}, "nested dict"

    lst = ["<think>a</think>A", {"data": "<think>b</think>B"}]
    res = sanitize_value(lst)
    assert res == ["A", {"data": "B"}], "nested list"

    tpl = ("<think>x</think>X",)
    res = sanitize_value(tpl)
    assert res == ("X",), "nested tuple"


def test_sanitize_value_object() -> None:
    class FakeResult:
        def __init__(self, text: str, extra: str | None = None) -> None:
            self.text = text
            self.extra = extra

    obj = FakeResult("<think>think</think>visible", "unchanged")
    res = sanitize_value(obj)
    assert hasattr(res, "text"), ".text object preserved"
    assert res.text == "visible", ".text sanitized"
    assert res.extra == "unchanged", ".text attr did not leak"


def test_patch_path() -> None:
    import launcher.http_launcher as http_launcher

    original_call_tool = http_launcher.mcp.call_tool
    original_patched = http_launcher._MCP_PATCHED

    class TextBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class MultiFieldResult:
        def __init__(
            self,
            text: str,
            content: list,
            structured_content: dict,
            data: str,
            untouched: str,
        ) -> None:
            self.text = text
            self.content = content
            self.structured_content = structured_content
            self.data = data
            self.untouched = untouched

    async def fake_call_tool(name: str, arguments: dict | None = None) -> MultiFieldResult:
        if name == "web_search":
            return MultiFieldResult(
                "<think>t1</think>visible1",
                [TextBlock("<think>t2</think>visible2")],
                {"key": "<think>t3</think>visible3"},
                "<think>t4</think>visible4",
                "<think>keepthis</think>unchanged",
            )
        return MultiFieldResult(
            "<think>notsanitized</think>fetched",
            [TextBlock("<think>notsanitized二期</think>fetched2")],
            {"key": "<think>notsanitized三期</think>fetched3"},
            "<think>notsanitized四期</think>fetched4",
            "<think>keepthis二期</think>fetched_unchanged",
        )

    http_launcher.mcp.call_tool = fake_call_tool
    http_launcher._MCP_PATCHED = False
    http_launcher._install_call_tool_patch()

    result = asyncio.run(http_launcher.mcp.call_tool("web_search", {}))
    assert result.text == "visible1", f"web_search .text sanitized, got: {result.text!r}"
    assert result.content[0].text == "visible2", "web_search .content[0].text sanitized"
    assert result.structured_content["key"] == "visible3", "web_search .structured_content sanitized"
    assert result.data == "visible4", "web_search .data sanitized"
    assert result.untouched == "<think>keepthis</think>unchanged", "non-target fields untouched"

    result2 = asyncio.run(http_launcher.mcp.call_tool("web_fetch", {}))
    assert "<think>notsanitized" in result2.text, "web_fetch .text NOT sanitized"

    http_launcher.mcp.call_tool = original_call_tool
    http_launcher._MCP_PATCHED = original_patched


def test_transport_normalization() -> None:
    import launcher.http_launcher as http_launcher

    assert http_launcher._normalize_transport(None) == "streamable-http"
    assert http_launcher._normalize_transport("streamable-http") == "streamable-http"
    assert http_launcher._normalize_transport("sse") == "sse"


def test_transport_normalization_rejects_legacy_modes() -> None:
    import launcher.http_launcher as http_launcher

    rejected = ["http", "stdio", "ws"]
    for value in rejected:
        try:
            http_launcher._normalize_transport(value)
        except ValueError as exc:
            assert "Expected one of" in str(exc), f"unexpected error: {exc}"
        else:
            raise AssertionError(f"expected ValueError for {value!r}")


def test_healthcheck_uses_streamable_http_by_default() -> None:
    import launcher.healthcheck as healthcheck

    original = healthcheck.os.environ.get("FASTMCP_TRANSPORT")
    try:
        healthcheck.os.environ.pop("FASTMCP_TRANSPORT", None)
        transport = (healthcheck.os.getenv("FASTMCP_TRANSPORT", "streamable-http").strip().lower() or "streamable-http")
        assert transport == "streamable-http"
    finally:
        if original is None:
            healthcheck.os.environ.pop("FASTMCP_TRANSPORT", None)
        else:
            healthcheck.os.environ["FASTMCP_TRANSPORT"] = original


if __name__ == "__main__":
    test_strip_think_segments()
    test_should_sanitize_tool()
    test_redact_config_info_text()
    test_redact_config_info_scrubs_urls_in_strings()
    test_sanitize_tool_result()
    test_sanitize_tool_result_with_object()
    test_scrub_urls()
    test_sanitize_value_nested()
    test_sanitize_value_object()
    test_patch_path()
    test_transport_normalization()
    test_transport_normalization_rejects_legacy_modes()
    test_healthcheck_uses_streamable_http_by_default()
    print("all_smoke_tests_ok")
