# GrokSearch Docker 远程 MCP 服务封装

## 1. 项目简介

本仓库是上游 `GrokSearch` 的 Docker 化远程 MCP 服务封装。

- 上游能力由 `GrokSearch` 子模块提供
- 包装层通过自有 launcher 复用上游 `grok_search.server:mcp` 实例
- 默认运行模式为 **远程 HTTP MCP 服务**，而不是 `stdio`
- 服务化逻辑尽量保留在包装层，避免将容器运行方式反写回上游子模块主逻辑

默认配置下，容器会监听：

- `http://0.0.0.0:8000/mcp`（容器内）
- 常见本地接入地址：`http://localhost:8000/mcp`

## 2. 接入模式概览

本镜像支持三种 MCP transport，通过环境变量 `FASTMCP_TRANSPORT` 切换：

| 模式 | 用途 | 默认值 | 说明 |
| --- | --- | --- | --- |
| HTTP | 远程接入，推荐 | 是 | 默认长期运行模式，适合 Docker / Compose / 反向代理场景 |
| SSE | 兼容模式，可选 | 否 | 兼容部分旧客户端；如客户端支持 HTTP，优先使用 HTTP |
| stdio | 兼容 / 调试 | 否 | 适合手动调试或由客户端拉起，不再是主路径 |

默认推荐模式：

- `FASTMCP_TRANSPORT=http`
- `FASTMCP_HOST=0.0.0.0`
- `FASTMCP_PORT=8000`
- `FASTMCP_PATH=/mcp`

## 3. 环境变量准备

先复制环境变量模板：

```bash
cp .env.example .env
```

至少需要准备以下变量：

```bash
GROK_SEARCH_IMAGE=ghcr.io/<repository-owner>/<repo-name>:latest
GROK_API_URL=https://your-api-endpoint.com/v1
GROK_API_KEY=your-grok-api-key
```

说明：

- `GROK_SEARCH_IMAGE`：Compose 使用的镜像地址
- `GROK_API_URL`：上游 Grok Search API 地址
- `GROK_API_KEY`：Grok Search API Key

FastMCP 服务相关变量如下：

```bash
FASTMCP_TRANSPORT=http
FASTMCP_HOST=0.0.0.0
FASTMCP_PORT=8000
FASTMCP_PATH=/mcp
FASTMCP_SHOW_BANNER=false
```

默认值与当前实现保持一致：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `FASTMCP_TRANSPORT` | `http` | 默认以远程 HTTP MCP 运行 |
| `FASTMCP_HOST` | `0.0.0.0` | 容器内监听地址 |
| `FASTMCP_PORT` | `8000` | 容器服务端口 |
| `FASTMCP_PATH` | `/mcp` | 默认 HTTP MCP 路径 |
| `FASTMCP_SHOW_BANNER` | `false` | 默认关闭启动 banner |

如果需要网页抓取与站点映射能力，还可以补充：

```bash
TAVILY_API_KEY=tvly-your-tavily-key
FIRECRAWL_API_KEY=your-firecrawl-api-key
```

## 4. 使用 Docker / Compose 启动服务

### Docker：默认 HTTP 服务模式

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
  ghcr.io/<repository-owner>/<repo-name>:latest
```

这会以默认配置启动长驻 HTTP MCP 服务，并监听：

- `http://localhost:8000/mcp`

### Docker Compose：默认 HTTP 服务模式

```bash
docker compose --env-file .env up -d
```

当前 `docker-compose.yml` 已按长驻服务模式配置：

- 暴露 `8000:8000`
- `restart: unless-stopped`
- 内置 `healthcheck`
- 保留非 root、只读根文件系统、`/tmp` tmpfs、配置卷挂载

Compose 会从 `GROK_SEARCH_IMAGE` 读取镜像地址；若未设置，会直接报错而不是静默使用错误镜像。

### stdio：兼容 / 调试用法

`stdio` 仍可通过环境变量启用，但不再是默认主路径。

例如：

```bash
docker run --rm -i \
  --env-file .env \
  -e FASTMCP_TRANSPORT=stdio \
  --read-only \
  --tmpfs /tmp \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  -v grok-search-config:/home/app/.config/grok-search \
  ghcr.io/<repository-owner>/<repo-name>:latest
```

如需切换到 SSE：

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
  ghcr.io/<repository-owner>/<repo-name>:latest
```

## 5. 健康检查与快速验证

### Compose 健康检查

`docker-compose.yml` 已内置 healthcheck：

- `http` 模式下会对 `http://127.0.0.1:8000/mcp` 执行最小探测
- `sse` 模式下会对默认 SSE endpoint `http://127.0.0.1:8000/sse` 执行最小探测
- `stdio` 模式下不提供网络健康检查，healthcheck 仅作兼容保留

查看容器状态：

```bash
docker compose ps
```

### 查看日志确认监听地址

```bash
docker logs grok-search
```

默认应看到服务监听 `/mcp` 路径，最终对外接入地址为：

- `http://localhost:8000/mcp`

### Python / FastMCP Client 快速验证

如果你的环境已安装 `fastmcp`，可以用最小客户端做探测：

```bash
python - <<'PY'
import anyio
from fastmcp import Client


async def main() -> None:
    async with Client("http://localhost:8000/mcp") as client:
        await client.ping()
        tools = await client.list_tools()
        print(f"tool_count={len(tools)}")


anyio.run(main)
PY
```

当前 CI 也会对 runtime 镜像执行 HTTP smoke test，覆盖：

- 容器启动
- 容器内 HTTP MCP endpoint 可达
- 宿主侧 `http://127.0.0.1:8000/mcp` 可达
- `ping + list_tools` 级别最小验证

## 6. Claude Code 远程接入（已确认）

**已确认能力**：Claude Code 支持将 MCP server 配置为 `http`、`sse`、`stdio` 三类 transport。

对于本仓库当前实现，推荐直接使用 **HTTP**：

- 默认 endpoint：`http://localhost:8000/mcp`
- 如服务同时支持 HTTP 与 SSE，应优先使用 HTTP
- SSE 已 deprecated，除兼容场景外不建议优先使用

### CLI 示例

```bash
claude mcp add --transport http grok-search http://localhost:8000/mcp
```

### JSON 示例

```json
{
  "type": "http",
  "url": "http://localhost:8000/mcp",
  "headers": {
    "Authorization": "Bearer <token-if-needed>"
  }
}
```

如果你的部署没有额外鉴权，可省略 `headers`。

## 7. Codex 远程接入（待验证兼容示例）

**待验证兼容示例**：公开 schema 显示 Codex 具备 MCP server 配置能力，常见字段可能包括：

- `url`
- `http_headers`
- `bearer_token_env_var`

但目前**未找到与 Claude Code 同等级、明确的远程 MCP 官方示例**，因此下面只能作为兼容性参考，**需以实际版本验证**，不代表官方已确认标准写法。

示例：

```json
{
  "url": "http://localhost:8000/mcp",
  "http_headers": {
    "Authorization": "Bearer ${MCP_AUTH_TOKEN}"
  },
  "bearer_token_env_var": "MCP_AUTH_TOKEN"
}
```

使用前请结合你实际使用的 Codex 版本、配置入口和 schema 校验结果确认字段格式。

## 8. 安全与部署建议

当前容器默认保留以下安全策略：

- 非 root 用户 `app`
- 只读根文件系统
- 丢弃全部 Linux capabilities
- `tmpfs /tmp`
- 配置目录持久化到 `/home/app/.config/grok-search`

部署建议：

- 优先在内网或受控网络中暴露服务
- 如需公网暴露，建议放在反向代理之后，并补充 TLS 与鉴权
- 如需访问宿主项目文件，请显式挂载目标目录，并按最小权限原则提供读写能力

### 关于 `toggle_builtin_tools` 的限制

`toggle_builtin_tools` 依赖项目工作区与 `.git`，会尝试向上查找项目根并读取或写入项目级设置。

默认服务容器通常**不会挂载宿主项目工作区**，因此：

- `status` 结果通常不能代表宿主项目的真实状态
- `on` / `off` 通常也无法直接修改宿主项目设置
- 仅挂载 `/home/app/.config/grok-search` 并不能满足该工具对项目目录与 `.git` 的要求

如果要让该工具真正作用于宿主项目，需要同时满足：

- 挂载目标项目目录
- 能从该目录向上找到 `.git`
- 提供足够的可写权限

## 9. 故障排查

### 容器启动后无法访问 `http://localhost:8000/mcp`

检查：

- 是否映射了 `-p 8000:8000`
- `FASTMCP_TRANSPORT` 是否仍为 `http`
- `FASTMCP_PORT` 与宿主映射是否一致
- `FASTMCP_PATH` 是否仍为 `/mcp`

### Compose 启动直接报镜像变量错误

请先在 `.env` 中设置：

```bash
GROK_SEARCH_IMAGE=ghcr.io/<repository-owner>/<repo-name>:latest
```

### healthcheck 异常

检查当前 transport：

- `http`：会对 `http://127.0.0.1:8000/mcp` 执行真实 endpoint 探测
- `sse`：会对 `http://127.0.0.1:8000/sse` 执行真实 endpoint 探测
- `stdio`：不提供网络健康检查，仅作兼容保留

### `toggle_builtin_tools` 状态与宿主项目不一致

这是默认行为。若未挂载宿主项目目录，容器内看到的路径状态通常不等于宿主项目真实状态。

### 需要切换 transport

可以通过环境变量切换：

```bash
FASTMCP_TRANSPORT=http
FASTMCP_TRANSPORT=sse
FASTMCP_TRANSPORT=stdio
```
