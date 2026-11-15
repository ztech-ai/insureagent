# 持久化适配层（待实现）

目标：SQLAlchemy / asyncpg 访问 PostgreSQL；提供租户限定的仓库和事务边界。每个并发任务独立会话，业务写入与 Outbox 在同一事务；模型输出不是数据库权威。

当前无连接、数据库密码或建表操作。按 docs/architecture/03_数据库与持久化.md 实施后加入根 Python 构建和依赖锁；迁移脚本放在 services/api/migrations。删除墓碑、来源版本及敏感字段加密必须先于真实数据接入完成。
