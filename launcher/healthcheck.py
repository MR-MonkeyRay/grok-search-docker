from __future__ import annotations

import os

import anyio


def _build_streamable_http_url() -> str:
    port = os.getenv("FASTMCP_PORT", "8000").strip() or "8000"
    path = (os.getenv("FASTMCP_PATH", "/mcp").strip() or "/mcp")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"http://127.0.0.1:{port}{path}"


def _build_sse_url() -> str:
    port = os.getenv("FASTMCP_PORT", "8000").strip() or "8000"
    return f"http://127.0.0.1:{port}/sse"


async def _probe_http() -> None:
    from fastmcp import Client

    async with Client(_build_streamable_http_url()) as client:
        await client.ping()


async def _probe_sse() -> None:
    from fastmcp import Client

    async with Client(_build_sse_url()) as client:
        await client.ping()


def main() -> int:
    transport = (os.getenv("FASTMCP_TRANSPORT", "streamable-http").strip().lower() or "streamable-http")
    if transport == "streamable-http":
        anyio.run(_probe_http)
        return 0
    if transport == "sse":
        anyio.run(_probe_sse)
        return 0

    raise SystemExit(f"Unsupported healthcheck transport: {transport!r}")


if __name__ == "__main__":
    raise SystemExit(main())
