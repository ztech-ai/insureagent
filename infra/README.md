# 内部 Alpha 基础设施

Compose 提供 PostgreSQL 17、API 和 Worker，API 仅绑定 127.0.0.1。先设置 `POSTGRES_PASSWORD`（URL 安全字符）、`ALPHA_DATA_KEY`（base64 32 字节随机密钥）和可选 `ASR_MODELS_DIR`（中文 Vosk 模型的父目录）。保留同一数据密钥，不提交环境文件。

```sh
docker compose -f infra/compose.yaml build
docker compose -f infra/compose.yaml up -d db
docker compose -f infra/compose.yaml run --rm api /app/.venv/bin/python scripts/alpha_admin.py init
docker compose -f infra/compose.yaml run --rm api /app/.venv/bin/python scripts/alpha_admin.py create-user --username alpha
docker compose -f infra/compose.yaml up -d api worker
```

开发网络需要自定义 CA 时，先构建同名镜像，再用 `up --no-build`：

```sh
docker build --secret id=ca_bundle,src=/path/to/ca-bundle.pem -f infra/docker/Dockerfile.api -t insureagent:alpha .
```

不关闭 TLS 验证，不把证书或凭据打入镜像。v1 schema 快照位于 migrations/；初始部署与已有 Alpha 加表由 CLI 显式执行，后续结构变化必须新增迁移。生产云资源、KMS、RLS、对象存储、区域恢复和容量配置按 RC 计划实施。

[完整运行手册](../docs/releases/alpha-runbook.md)
