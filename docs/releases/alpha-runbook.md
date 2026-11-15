# Alpha 0.1 运行与演示

仅使用虚构客户。Python 3.12、uv 0.13.6；移动端 Flutter 3.38.5。密钥、密码、录音、数据库和模型文件不提交 Git。

## 本机启动

```sh
uv sync --frozen --extra asr
export ALPHA_DATA_KEY="$(python -c 'import os,base64; print(base64.b64encode(os.urandom(32)).decode())')"
export DATABASE_URL=sqlite:///alpha.db
uv run --extra asr python scripts/alpha_admin.py init
uv run --extra asr python scripts/alpha_admin.py create-user --username alpha
uv run --extra asr uvicorn insureagent_api.main:app --host 127.0.0.1 --port 8000
```

密码交互输入。保存数据密钥到本机密钥服务／受控环境配置，重启使用同一密钥；密钥丢失不能解密旧数据。不要每次重启重新生成密钥。

另一个终端加载相同数据库、密钥配置：

```sh
export VOSK_MODEL_PATH=/absolute/path/vosk-model-small-cn-0.22
uv run --extra asr python scripts/run_worker.py
```

模型下载入口：https://alphacephei.com/vosk/models 。选择中文模型，解压后设置目录。没有模型时文字链路可用；语音仍可保存，处理显示失败，可手动补转写或配置模型后重试。当前合成语音初评不达标，见验收记录。

可选本机 Ollama：在同一主机运行 Ollama 并准备模型，设置 `ALPHA_EXTRACTOR=ollama`、`ALPHA_MODEL=<已安装模型名>`；默认端点 `http://127.0.0.1:11434/api/chat`。仅接受本机 HTTP 地址，禁用代理和重定向。错误输出／超时会保留记录并显示失败，不默默切换为模型成功。Docker 中的 localhost 是容器本身；默认 Compose 只启用规则提取。

## 移动端

```sh
cd apps/mobile
flutter pub get
flutter run --dart-define=API_URL=https://your-private-alpha-api.example
```

Android 模拟器本机开发可使用 debug 默认 `http://10.0.2.2:8000`；iOS 默认 ATS 不允许 HTTP，请配置受信任 HTTPS。正式构建仅允许 HTTPS。Android 最低 API 23，iOS 工程最低 13.0；需用真机验证插件兼容性。iOS Keychain entitlement 已添加，设备安装仍需自己的 Apple 签名配置。Android debug APK 只用于内部验证。

## 演示脚本

1. 登录内部账户，新建两个同名客户并添加区分备注；确认系统不会自动合并。
2. 飞行模式录一段虚构客户接触或输入文字，保存草稿；重启应用确认仍可恢复。
3. 恢复网络并上传。确认“已保存”先出现，处理失败时记录仍可见；重复上传同一 UUID 不新增记录。
4. 单人记录：选客户确认归属，再选择事实确认。检查归属操作不会自动确认事实。
5. 多人记录：每句只描述一人，逐组勾选来源片段，选择客户并分配，然后分别确认事实。混合一人的句子可先更正原文拆句。
6. 到客户档案核对证据和时间线；更正原文、撤销确认或撤销归属，确认旧事实不继续显示为有效。
7. 建立手动任务，延期、完成并记录结果；销售阶段不自动变化。
8. 删除记录后，旧 UUID 重放返回 410；跨账户无法读取其客户、记录、音频或事实。

## 验证命令

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python scripts/alpha_smoke.py
uv run python scripts/evaluate_alpha.py
uv run python scripts/export_contracts.py
git diff --exit-code -- contracts
cd apps/mobile
flutter analyze
flutter test
```

PostgreSQL 重跑：设置 `TEST_DATABASE_URL=postgresql+psycopg://.../test_database` 后运行 pytest；测试每例建立随机 schema 并在结束后删除，必须使用专用测试数据库及有建 schema 权限的账户。

## 真机验收表（执行时填写设备、OS、结果及缺陷）

| 场景 | 预期 |
| --- | --- |
| 拒绝麦克风 | 明确提示，可返回文字记录 |
| 来电／应用切后台／锁屏 | 停止录音，已写入加密片段可恢复，不声称后台持续录音 |
| 强杀后重启 | 草稿可恢复；恢复音频上传前提醒可能缺少末尾 |
| 无网／请求完成但响应丢失 | 草稿保留，重试同 UUID 不重复创建 |
| 磁盘满／片段缺失／密文损坏 | 显示错误，不能静默上传不完整音频 |
| A 退出、B 登录 | B 看不到 A 草稿和正在返回的云端列表 |
| iOS Keychain／Android Keystore 重启 | 同账户草稿密钥可读；Android 自动备份关闭 |

## 运维和恢复

`/health/live` 检查进程，`/health/ready` 检查配置和数据库可访问。API 不自动建表，先执行 `alpha_admin.py init`。初始化为 v1 schema 账本，PostgreSQL SQL 快照见 `infra/migrations/0001_alpha.sql`；后续变更新增迁移，不修改已部署基线。

单独备份数据库与密钥；Alpha 不承诺备份中的删除传播。发布前停止写入、备份、初始化／升级、启动 Worker/API，再跑健康及演示。回滚程序必须与 schema 版本兼容；不自动执行破坏性降级。测试完成可删除专用测试数据库和模型；勿删除共享数据库或密钥。

故障诊断只记录 request ID、状态码和 error_code，不打印客户原文、密码、Bearer token 或音频。完整生产监控、灾备、密钥轮换和容量验证按 RC 计划继续。
