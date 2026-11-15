# 移动端 Alpha

Flutter 3.38.5；真实 API 登录、录音／文字、按账户加密草稿、上传重试、客户档案、片段归属、事实确认／撤回和手动任务。

```sh
flutter pub get
flutter analyze
flutter test
flutter run --dart-define=API_URL=https://your-private-alpha-api.example
```

Android debug 模拟器可用默认 http://10.0.2.2:8000；iOS 使用受信任 HTTPS。API 账号由服务器 CLI 创建。Android 最低 API 23，iOS 最低 13.0；密钥存储与录音插件必须真机验证。签名与商店发布不包含在内部 Alpha 中。

构建：`flutter build apk --debug`；macOS 上 `flutter build ios --simulator --debug`。CI 保存构建产物。不要将 debug 签名包作为商店版本。

[运行手册及真机矩阵](../../docs/releases/alpha-runbook.md) · [验收状态](../../docs/releases/alpha-progress.md)
