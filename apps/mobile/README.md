# 移动端

Flutter 3.38.5 初始骨架，选择为待 W2 真机验证的工程起点，见 ADR-001。四个导航入口可运行，但没有真实录音、账号、支付或网络处理。

```sh
cd apps/mobile
flutter pub get
flutter analyze
flutter test
flutter run
```

ios/、android/ 已由 Flutter 3.38.5 生成。原生构建需要 Android SDK 或 macOS + Xcode；签名、商店包名、录音权限和真机验收仍待实施。当前包名仅为工程占位，禁止提交签名密钥。
