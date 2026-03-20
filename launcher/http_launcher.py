from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
GROKSEARCH_SRC = REPO_ROOT / "GrokSearch" / "src"
if GROKSEARCH_SRC.exists() and str(GROKSEARCH_SRC) not in sys.path:
    sys.path.insert(0, str(GROKSEARCH_SRC))

from grok_search.server import mcp


VALID_TRANSPORTS = {"http", "sse", "stdio"}


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(
        "Invalid FASTMCP_SHOW_BANNER value: "
        f"{value!r}. Expected one of true/false/1/0/yes/no/on/off."
    )


def _normalize_transport(value: str | None) -> str:
    transport = (value or "http").strip().lower()
    if transport not in VALID_TRANSPORTS:
        valid = ", ".join(sorted(VALID_TRANSPORTS))
        raise ValueError(
            f"Invalid FASTMCP_TRANSPORT value: {transport!r}. Expected one of: {valid}."
        )
    return transport


def _parse_port(value: str | None) -> int:
    raw = (value or "8000").strip()
    try:
        port = int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid FASTMCP_PORT value: {raw!r}. Expected an integer.") from exc

    if not (1 <= port <= 65535):
        raise ValueError(
            f"Invalid FASTMCP_PORT value: {raw!r}. Expected an integer between 1 and 65535."
        )
    return port


def _normalize_path(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "/mcp"
    if raw == "/":
        return "/"
    return raw if raw.startswith("/") else f"/{raw}"


def _apply_setting(name: str, value: Any) -> None:
    settings = getattr(mcp, "settings", None)
    if settings is None or not hasattr(settings, name):
        return
    setattr(settings, name, value)


def _supported_kwargs() -> set[str]:
    try:
        return set(inspect.signature(mcp.run).parameters)
    except (TypeError, ValueError):
        return set()


def _resolve_transport(requested: str) -> str:
    try:
        annotation = inspect.signature(mcp.run).parameters["transport"].annotation
    except (KeyError, TypeError, ValueError):
        return requested

    annotation_text = str(annotation)
    if requested == "http" and "streamable-http" in annotation_text and '"http"' not in annotation_text:
        return "streamable-http"
    return requested


def _run_mcp(**kwargs: Any) -> None:
    supported_kwargs = _supported_kwargs()
    if supported_kwargs:
        kwargs = {key: value for key, value in kwargs.items() if key in supported_kwargs}
    mcp.run(**kwargs)


def main() -> int:
    try:
        transport = _normalize_transport(os.getenv("FASTMCP_TRANSPORT", "http"))
        show_banner = _parse_bool(os.getenv("FASTMCP_SHOW_BANNER"), default=False)

        if transport == "stdio":
            _run_mcp(transport="stdio", show_banner=show_banner)
            return 0

        host = os.getenv("FASTMCP_HOST", "0.0.0.0")
        port = _parse_port(os.getenv("FASTMCP_PORT", "8000"))
        _apply_setting("host", host)
        _apply_setting("port", port)

        resolved_transport = _resolve_transport(transport)
        run_kwargs: dict[str, Any] = {
            "transport": resolved_transport,
            "host": host,
            "port": port,
            "show_banner": show_banner,
        }

        if transport == "http":
            path = _normalize_path(os.getenv("FASTMCP_PATH"))
            _apply_setting("streamable_http_path", path)
            run_kwargs["path"] = path

        _run_mcp(**run_kwargs)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"launcher error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
