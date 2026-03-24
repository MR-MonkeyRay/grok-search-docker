# GrokSearch Docker MCP

基于上游 `GrokSearch` 的 Docker 封装，提供远程 MCP 服务。

## 核心信息

- 仅支持两种启动模式：`streamable-http`、`sse`
- 默认模式：`streamable-http`
- 默认地址：`http://localhost:8000/mcp`

## 必填环境变量

```bash
GROK_SEARCH_IMAGE=ghcr.io/mr-monkeyray/grok-search-docker:latest
GROK_API_URL=https://your-api-endpoint.com/v1
GROK_API_KEY=your-grok-api-key
```

## MCP 相关变量

```bash
FASTMCP_TRANSPORT=streamable-http
FASTMCP_HOST=0.0.0.0
FASTMCP_PORT=8000
FASTMCP_PATH=/mcp
FASTMCP_SHOW_BANNER=false
```

说明：

- `streamable-http` 使用 `FASTMCP_PATH`，默认 `/mcp`
- `sse` 固定使用 `/sse`

## 启动

先准备环境变量：

```bash
cp .env.example .env
```

Docker Compose：

```bash
docker compose --env-file .env up -d
```

Docker：

```bash
docker run -d \
  --name grok-search \
  --env-file .env \
  --read-only \
  --tmpfs /tmp \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  -p 8000:8000 \
  -v grok-search-config:/home/app/.config/grok-search \
  ghcr.io/mr-monkeyray/grok-search-docker:latest
```

切换到 `sse`：

```bash
docker run -d \
  --name grok-search-sse \
  --env-file .env \
  -e FASTMCP_TRANSPORT=sse \
  -p 8000:8000 \
  --read-only \
  --tmpfs /tmp \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  -v grok-search-config:/home/app/.config/grok-search \
  ghcr.io/mr-monkeyray/grok-search-docker:latest
```

## 健康检查

- `streamable-http`：探测 `http://127.0.0.1:8000/mcp`
- `sse`：探测 `http://127.0.0.1:8000/sse`

## Claude Code 接入

`streamable-http`：

```bash
claude mcp add --transport http grok-search http://localhost:8000/mcp
```

`sse`：

```bash
claude mcp add --transport sse grok-search http://localhost:8000/sse
```
