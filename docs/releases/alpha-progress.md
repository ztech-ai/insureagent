# Alpha 实施记录（进行中）

目标是开发计划 W10 的内部合成数据 Alpha，尚未完成 G2 验收。

## 已实现的第一批后端能力

- CLI 创建内部账户；scrypt 密码摘要、随机会话 token 的 SHA-256 存储、退出失效。
- SQLAlchemy 租户复合键、事务及 AES-256-GCM 加密实体载荷，AAD 绑定租户、类型和 ID。
- 文本记录持久化及 client_record_id 幂等；业务写入与 Job、Outbox 同事务。
- 数据库队列领取、租约、fencing、修订校验；提取失败保留已保存记录并允许重试。
- 人物候选、事实候选／确认分离；记录更正或移客户后撤回旧事实；关键词历史检索。
- 客户档案、时间线、手动任务完成／延期／取消和联系结果。
- 本地规则提取和数字形式标识符脱敏基线。无第三方模型调用；规则精度不能替代 AI/DLP 验收。

## 当前运行方式

设置 DATABASE_URL（默认 sqlite:///alpha.db，仅本机开发）和 ALPHA_DATA_KEY（base64 编码 32 字节随机密钥，放入环境变量／密钥服务，勿提交）。

```sh
uv sync --frozen
uv run python scripts/alpha_admin.py init
uv run python scripts/alpha_admin.py create-user --username alpha
uv run uvicorn insureagent_api.main:app --host 127.0.0.1
# 另一个配置相同环境变量的终端
uv run python scripts/run_worker.py
```

账户密码交互输入。生产环境、KMS、RLS、正式迁移、托管队列和第三方模型均未验收，不能开放公网或录入真实资料。

## 后续必须继续完成

1. 移动端登录与真实 API、客户及记录详情、逐项确认／更正、任务交互。
2. 移动端加密离线草稿与幂等续传、录音及中断恢复、服务器加密音频、受控本地 ASR。
3. 多人物片段归属、任务写入幂等、基础用量、登录限流、统一 request_id／错误响应。
4. PostgreSQL 集成、迁移基线、并发和音频边界测试；处理状态、失败阶段与计量闭环。
5. 模型适配和受控评测（规则基线不等同模型实现）；演示、启动文档、CI 和 Alpha 验收矩阵。

当前移动端仍为初始化导航骨架；不得将本阶段后端提交描述成完整 Alpha。
