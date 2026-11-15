# 交互原型

所有姓名与内容均为虚构。HTML 原型不录音、不支付、不外发消息；APP 的实现状态见仓库主 README。

原验证脚本已调整为使用 Playwright 管理的 Chromium，以便跨机器运行：

```sh
uv sync --group prototype
uv run playwright install chromium
uv run python design/prototype/验证与截图.py
```

会重新生成本目录的截图和验证结果，请检查 diff 后再提交。原型的 HTML 保留为可嵌入片段，浏览器可以直接打开。
