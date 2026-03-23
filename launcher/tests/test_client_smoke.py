from __future__ import annotations

import anyio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastmcp import Client


async def list_tools(url: str) -> None:
    async with Client(url) as client:
        tools = await client.list_tools()
        print(f"container_tool_count={len(tools)}")


async def ping(url: str) -> None:
    async with Client(url) as client:
        await client.ping()
        print("host_http_ping_ok")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: test_client_smoke.py <list-tools|ping> <url>", file=sys.stderr)
        sys.exit(1)

    mode = sys.argv[1]
    url = sys.argv[2]

    if mode == "list-tools":
        anyio.run(list_tools, url)
    elif mode == "ping":
        anyio.run(ping, url)
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        sys.exit(1)
