# Lumina API — 本地开发镜像（配合 compose 挂载源码实现热加载）
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LLM_CONFIG_PATH=/app/infra/config/llm.yaml

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY apps ./apps
COPY packages ./packages
COPY infra ./infra
COPY data ./data
COPY static ./static
COPY tests ./tests

RUN pip install --upgrade pip \
    && pip install -e ".[dev]"

EXPOSE 8000

# 默认无 --reload；compose 开发覆盖为带 reload 的命令
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "apps/api/src"]
