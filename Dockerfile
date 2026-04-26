# Lumina API — 本地构建与分发镜像（完整打包，可直接导出）
# 使用方式:
#   docker build -t lumina:latest .
#   docker save lumina:latest -o lumina-image.tar
#
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LLM_CONFIG_PATH=/app/infra/config/llm.yaml \
    INTENT_RULES_PATH=/app/config/intent_rules.yaml \
    AGENTS_CONFIG_PATH=/app/config/agents.yaml

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖配置（利用 Docker 缓存层）
COPY pyproject.toml README.md ./

# 复制项目源码
COPY apps ./apps
COPY packages ./packages
COPY skills ./skills
COPY infra ./infra
COPY config ./config
COPY data ./data
COPY static ./static

# 安装 Python 依赖（生产镜像不安装 dev 依赖）
RUN pip install --upgrade pip \
    && pip install -e "."

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "apps/api/src"]
