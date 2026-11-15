# 开发约定

先阅读 README、开发计划和相关详细设计，再按需求编号创建功能分支。PR 说明需求、行为、验证及风险；不要把设计更新记作功能完成。

执行 `uv sync --frozen`、`make lint`、`make test`；修改接口后运行 `make contracts`。移动端执行 flutter analyze 和 flutter test。新增依赖更新并提交 uv.lock。

所有测试数据必须是合成数据；不提交客户语音、证件、手机号、真实导出、凭证及签名。认证、隐私、计费和迁移改动须专业复核。CI 不自动部署。
