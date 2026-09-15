# Lumina API — 本地构建与分发镜像（完整打包，可直接导出）
# 使用方式:
#   docker build -t lumina:latest .
#   docker save lumina:latest -o lumina-image.tar
#
# 注意：密钥类环境变量（DEEPSEEK_API_KEY 等）请在运行容器时通过 env_file 或 -e 注入，
#       不要写入 Dockerfile，避免泄漏到镜像层。
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LLM_CONFIG_PATH=/app/infra/config/llm.yaml

WORKDIR /app

RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update -o Acquire::Max-FutureTime=3600 \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖配置（利用 Docker 缓存层）
COPY pyproject.toml README.md ./

# 复制项目源码
COPY apps ./apps
COPY packages ./packages
COPY infra ./infra
COPY config ./config
COPY data ./data
COPY static ./static
# Hermes Agent 底座（唯一执行引擎，vendor 钉版本）
COPY vendor ./vendor

# 安装 Python 依赖（生产镜像不安装 dev 依赖）
# 使用国内 PyPI 镜像并加大超时，避免 playwright 等大包下载中断
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=5
RUN pip install --upgrade pip -i ${PIP_INDEX_URL} \
    && pip install -e "." -i ${PIP_INDEX_URL}

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "apps/api/src"]
