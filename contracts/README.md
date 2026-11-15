# 接口契约

`uv run python scripts/export_contracts.py` 从源码生成 OpenAPI 与事件 JSON Schema，CI 检查生成结果一致。

OpenAPI 目前仅描述已实现的健康检查；规划业务接口位于 docs/architecture，不能把规划接口当作已上线功能。事件只含元数据，消费端仍须验证租户、当前版本、策略及租约。
