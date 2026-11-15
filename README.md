# 保知伴 AI · InsureAgent

保险销售人员的个人 AI 客户经营助手。采用 iOS / Android APP 与云端受控 Agent，支持记录、客户档案、经营建议和跟进闭环。

**当前为内部 Alpha 0.1，不能用于真实客户资料或商用。** 已实现移动端和云端核心记录闭环；真机、ASR/模型质量与 G2 人工验收仍待完成，详见 [实施与验收记录](docs/releases/alpha-progress.md)。

## 仓库结构

| 目录 | 内容 |
| --- | --- |
| `apps/mobile/` | Flutter 移动端源码，按今天、客户、跟进、我的及记录／确认／助手等功能分目录 |
| `services/api/` | FastAPI；identity、customers、records、tasks、billing、privacy、insights 业务模块 |
| `services/worker/` | 异步任务入口；记录、建议、通知、删除任务边界 |
| `packages/domain/` | 独立领域模型、记录状态与事件契约 |
| `packages/persistence/` | 数据访问与迁移实施入口（待实现） |
| `packages/ai/` | 模型网关以及 ASR、DLP、提取、检索和建议适配层 |
| `contracts/` | 自动生成的 OpenAPI 和事件 JSON Schema |
| `infra/` | 本地容器配置和后续云部署入口 |
| `docs/product/` | 完整产品需求 |
| `docs/architecture/` | 00–11 详细设计、评审、UI 规范及开发计划；成本计算脚本 |
| `docs/planning/` | 7 张开发任务／验收 CSV 及计划校核记录 |
| `docs/adr/` | 架构决策和选型状态 |
| `design/prototype/` | 可交互 HTML 原型、13 张截图、验证脚本及原验证结果 |
| `evals/` | AI 评测规范及合成事件样例 |
| `tests/`、`scripts/` | 工程测试及契约生成工具 |

## Alpha 0.1

已实现内部合成数据的记录、语音转写、人工归属及事实确认、档案证据、纠错和手动任务闭环。移动端为 Flutter 真实 API 客户端，含加密离线草稿及录音；后端为 FastAPI + PostgreSQL/SQLite + 独立 Worker。

- [运行与演示手册](docs/releases/alpha-runbook.md)
- [实施范围、验证结果与 G2 待验收项](docs/releases/alpha-progress.md)
- [移动端构建](apps/mobile/README.md)
- [容器启动](infra/README.md)

```sh
uv sync --frozen
uv run pytest -q
uv run python scripts/alpha_smoke.py
```

默认规则提取，可选 Vosk 本地转写和 Ollama 来源片段筛选。测试不需要第三方模型密钥。真实语音准确率、真机录音和目标用户可用性仍需验收，不能用于真实客户资料或收费。

## 设计与计划

- [产品需求与系统设计](docs/product/保险销售AI助手_需求与系统设计.md)
- [架构与设计索引](docs/architecture/00_设计总览与技术选型.md)
- [20 周开发计划](docs/architecture/11_产品开发计划.md)
- [UI 交互规范](docs/architecture/10_移动端交互与界面规范.md)
- [WBS 与工时](docs/planning/WBS工作包与工时.csv)
- [需求与验收追踪](docs/planning/需求与验收追踪.csv)

文档和原型来自此前设计交付，截图／验证结果已在本次初始化重新回归，不代表移动端业务实现。Git 中的版本用于工程评审，原 Pages 链接作为来源保留；文档内链接已改为仓库相对路径。

参阅 [贡献说明](CONTRIBUTING.md)、[安全说明](SECURITY.md) 和 [Apache 2.0 许可证](LICENSE)。
