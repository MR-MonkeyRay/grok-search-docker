# GrokSearch Docker 使用说明

## 1. 准备环境变量

复制一份环境变量模板：

```bash
cp .env.example .env
```

至少填写以下 3 个变量：

```bash
GROK_SEARCH_IMAGE=ghcr.io/<repository-owner>/<repo-name>:latest
GROK_API_URL=https://your-api-endpoint.com/v1
GROK_API_KEY=your-grok-api-key
```

其中：

- `GROK_SEARCH_IMAGE` 用于 Compose 显式指定镜像地址，避免误拉取错误仓库镜像
- 如果你使用当前仓库对应的 GHCR 镜像，请填写为实际全小写的最终镜像名 `ghcr.io/<repository-owner>/<repo-name>:latest`
- 镜像路径会自动使用当前仓库的 owner 与仓库名生成；最终镜像全名会在 workflow 中统一转小写后再推送
- Compose 不会自动转小写，因此运行侧填写 `GROK_SEARCH_IMAGE` 时也必须使用实际全小写名称

如果需要网页抓取与站点映射，再补充：

```bash
TAVILY_API_KEY=tvly-your-tavily-key
FIRECRAWL_API_KEY=your-firecrawl-api-key
```

## 2. 拉取镜像

默认路径是直接消费 GHCR 的 `latest` 镜像，无需先本地构建。
当前环境需要能够访问当前仓库对应的 GHCR 包：`ghcr.io/<repository-owner>/<repo-name>:latest`。其中 `<repository-owner>` 为当前仓库 owner，`<repo-name>` 为当前仓库名。workflow 会将最终镜像全名统一转小写后再推送，但运行侧不会自动转小写，因此实际拉取时也必须使用全小写镜像名。

```bash
docker pull ghcr.io/<repository-owner>/<repo-name>:latest
```

## 3. 运行方式

这是一个 `stdio` MCP 服务，不会暴露 HTTP 端口，适合由 MCP Client 拉起。

直接运行 GHCR `latest` 镜像（与当前 Compose 安全策略对齐）：

```bash
docker run --rm -i \
  --env-file .env \
  --read-only \
  --tmpfs /tmp \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  -v grok-search-config:/home/app/.config/grok-search \
  ghcr.io/<repository-owner>/<repo-name>:latest
```

使用 Compose 运行：

```bash
docker compose --env-file .env run --rm grok-search
```

Compose 会从 `GROK_SEARCH_IMAGE` 读取镜像地址；如果未设置，该命令会直接报错并提示补齐变量，而不是静默使用错误的默认镜像。

## 4. 测试

运行测试镜像：

```bash
docker build --target test -t grok-search-mcp:test-suite .
docker run --rm grok-search-mcp:test-suite
```

## 5. 自动同步与发布（CI）

仓库会通过 `.github/workflows/sync-build-publish.yml` 定时同步 `GrokSearch` submodule，并在检测到上游变更、目标 `sha-<commit>` 镜像不存在，或手动触发 `force_publish=true` 时发布镜像。

发布规则：

- 发布前会先构建并运行 `test` stage，并做最小 smoke check；验证失败不会推送任何镜像
- 如果 submodule 指针发生变化，会先完成仓库内的 submodule bump 提交与推送，再执行镜像推送，避免出现“镜像已发但仓库未同步”
- GHCR 登录用户名仍使用 `${{ github.actor }}`，镜像路径会自动使用当前仓库 owner 与仓库名拼出 `ghcr.io/<repository-owner>/<repo-name>`，并在推送前对完整镜像名整体转为小写
- 标签策略：始终发布 `latest` 与不可变的 `sha-<commit>`；仅当 `pyproject.toml` 的 `version` 发生变化、目标 `sha-<commit>` 镜像不存在，或手动触发 `force_publish=true` 时，才发布 `v<version>`

## 6. 当前容器策略

- 运行用户为非 root `app`
- 根文件系统为只读
- 丢弃全部 Linux capabilities
- 使用 `tmpfs` 提供 `/tmp`
- 配置目录持久化到 `/home/app/.config/grok-search`

## 7. 关于 toggle_builtin_tools 的限制

`toggle_builtin_tools` 会通过 `.git` 向上查找项目根，并读取或写入项目级 `.claude/settings.json`。

默认容器运行方式通常没有挂载宿主项目工作区，因此：

- `status` 只能反映容器当前环境中推导出的路径状态，通常不能代表宿主项目的真实设置
- `on` / `off` 即使返回的是结构化错误信息，也通常无法修改宿主项目，因为默认容器既没有对应项目目录，也启用了只读根文件系统

如果你要查看或修改宿主项目状态，请挂载对应项目目录。

建议：

- 默认容器运行方式下，不要把 `status` 的结果当作宿主项目设置
- 如果要查看宿主项目状态，请将目标项目目录挂载进容器，并保证工具能从该目录向上找到 `.git`
- 如果要执行 `on` / `off`，除了挂载目标项目目录，还需要提供可写挂载，或关闭容器只读限制
- 仅挂载 `/home/app/.config/grok-search` 不能满足该工具的项目级读取/写入需求
