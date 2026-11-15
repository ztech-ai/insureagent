import 'package:flutter/material.dart';
import '../../core/controller.dart';
import '../../core/widgets.dart';

class ProfilePage extends StatelessWidget {
  final AlphaController controller;
  const ProfilePage({super.key, required this.controller});
  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      section(
        '内部 Alpha',
        Text(
          '账号：${controller.username}\n服务：${controller.api?.base.origin}\n仅使用虚构客户与合成数据。',
        ),
      ),
      section(
        '隐私与处理方式',
        const Text(
          '本机草稿按账号加密；口述仅在你点击上传后发送给当前服务。本地 ASR 在该服务上处理原音频，未接入第三方模型。\n退出后云端列表从界面清除；加密草稿保留，仅同一账号登录后可恢复。',
        ),
      ),
      FilledButton.tonal(
        onPressed: () => act(context, controller.refresh),
        child: const Text('重新连接并刷新'),
      ),
      const SizedBox(height: 16),
      OutlinedButton(
        onPressed: () => act(context, controller.logout),
        child: const Text('退出并清除本机会话'),
      ),
    ],
  );
}
