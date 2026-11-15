# 保知伴 AI · InsureAgent

保险销售人员的个人 AI 客户经营助手。采用 iOS / Android APP 与云端受控 Agent，支持记录、客户档案、经营建议和跟进闭环。

**当前正在开发内部 Alpha，不是可商用 APP。** 进展及运行方式见 [Alpha 实施记录](docs/releases/alpha-progress.md)。以下初始化说明作为起点；新后端已支持文本记录闭环，移动端、语音和完整验收仍在实施。

**初始化基线：** 已归档需求、设计、原型和开发计划；API 健康检查、领域状态与事件契约、禁用的模型网关、离线事件校验入口和移动端四栏导航已建立。认证、数据库、录音、模型处理、订阅及生产部署仍待开发，禁止接入真实客户资料。

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

## 快速启动

需要 Python 3.12 和 uv。依赖通过 uv.lock 固定。

```sh
uv sync --frozen
make test
make lint
make api
```

打开 http://127.0.0.1:8000/docs 。`/health/live` 返回 200；`/health/ready` 返回 503，表示持久化、鉴权等生产依赖尚未实现。

```sh
make prototype
# 浏览器打开 http://127.0.0.1:8080/insurance-mobile.html
```

移动端初始化及运行见 [mobile README](apps/mobile/README.md)；本地容器见 [infra README](infra/README.md)。不需要配置模型密钥即可执行现有测试。

## 设计与计划

- [产品需求与系统设计](docs/product/保险销售AI助手_需求与系统设计.md)
- [架构与设计索引](docs/architecture/00_设计总览与技术选型.md)
- [20 周开发计划](docs/architecture/11_产品开发计划.md)
- [UI 交互规范](docs/architecture/10_移动端交互与界面规范.md)
- [WBS 与工时](docs/planning/WBS工作包与工时.csv)
- [需求与验收追踪](docs/planning/需求与验收追踪.csv)

文档和原型来自此前设计交付，截图／验证结果已在本次初始化重新回归，不代表移动端业务实现。Git 中的版本用于工程评审，原 Pages 链接作为来源保留；文档内链接已改为仓库相对路径。

参阅 [贡献说明](CONTRIBUTING.md)、[安全说明](SECURITY.md) 和 [Apache 2.0 许可证](LICENSE)。
