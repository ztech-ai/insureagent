# 基础设施

`docker compose -f infra/compose.yaml up --build` 启动本地 API（127.0.0.1:8000）。当前只验证进程存活，就绪检查返回 503 是预期结果。

生产云资源尚未配置。PostgreSQL、Redis、RabbitMQ、OSS、KMS、双可用区与跨区灾备按设计单独实施；本目录不包含云凭证，不会创建收费资源。

若开发网络使用自定义 CA，构建时可通过 BuildKit secret 注入信任证书（不写入镜像或仓库）：

```sh
docker build --secret id=ca_bundle,src=/path/to/ca-bundle.pem -f infra/docker/Dockerfile.api -t insureagent-api:bootstrap .
```

标准网络无需传入此参数，不关闭 TLS 验证。
