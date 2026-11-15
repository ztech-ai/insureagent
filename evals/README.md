# AI 评测

评测按脱敏、客户识别、事实抽取、证据引用和提示注入分组。训练／提示词调优集与留出集必须隔离并版本化；当前未提供有统计代表性的业务评测集。

fixtures 仅有合成事件样例，用于 Worker 契约检查，不可作为 AI 质量证据。

```sh
uv run insureagent-worker --validate-event < evals/fixtures/record-stored.json
```

正式评测样本、门槛和准入条件见开发计划第 8–9 节。
