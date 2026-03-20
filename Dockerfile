FROM python:3.11-slim AS builder

ARG GROKSEARCH_VERSION=

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY GrokSearch/ ./groksearch-src/

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install ./groksearch-src


FROM builder AS test

COPY launcher/ /build/launcher/

RUN /opt/venv/bin/pip install ./groksearch-src[dev]

CMD ["/bin/sh", "-lc", "set -e; cd /build/groksearch-src; /opt/venv/bin/python -m compileall -q src; /opt/venv/bin/python -m compileall -q /build/launcher; /opt/venv/bin/python -c \"import grok_search.server\"; PYTHONPATH=/build:/build/groksearch-src/src /opt/venv/bin/python -c \"import launcher.http_launcher; import launcher.healthcheck\"; set +e; /opt/venv/bin/pytest -q; status=$?; set -e; if [ $status -eq 0 ]; then exit 0; fi; if [ $status -eq 5 ]; then echo 'pytest: no tests collected; compatibility policy allows publish to continue'; exit 0; fi; exit $status"]


FROM python:3.11-slim AS runtime

ARG GROKSEARCH_VERSION=

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/opt/venv/bin:$PATH" \
    GROK_LOG_DIR=logs \
    FASTMCP_TRANSPORT=http \
    FASTMCP_HOST=0.0.0.0 \
    FASTMCP_PORT=8000 \
    FASTMCP_PATH=/mcp \
    FASTMCP_SHOW_BANNER=false

LABEL org.opencontainers.image.title="grok-search-mcp" \
      org.opencontainers.image.description="Docker image for GrokSearch MCP server" \
      org.opencontainers.image.version="$GROKSEARCH_VERSION"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --home-dir /home/app --shell /usr/sbin/nologin app \
    && mkdir -p /home/app/.config/grok-search /app \
    && chown -R app:app /home/app /app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY launcher/ /app/launcher/

EXPOSE 8000

USER app

ENTRYPOINT ["python", "/app/launcher/http_launcher.py"]
