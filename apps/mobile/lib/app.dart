import 'package:flutter/material.dart';
import 'core/controller.dart';
import 'features/today/today_page.dart';
import 'features/customers/customers_page.dart';
import 'features/tasks/tasks_page.dart';
import 'features/profile/profile_page.dart';

class InsureAgentApp extends StatefulWidget {
  final AlphaController? controller;
  const InsureAgentApp({super.key, this.controller});
  @override
  State<InsureAgentApp> createState() => _InsureAgentAppState();
}

class _InsureAgentAppState extends State<InsureAgentApp> {
  late final AlphaController controller;
  int index = 0;
  @override
  void initState() {
    super.initState();
    controller = widget.controller ?? AlphaController();
    if (widget.controller == null) controller.restore();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: '保知伴 AI',
    theme: ThemeData(
      colorSchemeSeed: const Color(0xff22634b),
      useMaterial3: true,
      scaffoldBackgroundColor: const Color(0xfff5f7f3),
    ),
    home: AnimatedBuilder(
      animation: controller,
      builder: (context, _) => !controller.loggedIn
          ? LoginPage(controller: controller)
          : Scaffold(
              appBar: AppBar(
                title: const Text('保知伴 AI · 内部 Alpha'),
                actions: [
                  IconButton(
                    onPressed: controller.refresh,
                    icon: const Icon(Icons.refresh),
                  ),
                ],
              ),
              body: Column(
                children: [
                  if (controller.busy) const LinearProgressIndicator(),
                  if (controller.notice != null)
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(12),
                      color: Theme.of(context).colorScheme.errorContainer,
                      child: Text(controller.notice!),
                    ),
                  Expanded(
                    child: IndexedStack(
                      index: index,
                      children: [
                        TodayPage(controller: controller),
                        CustomersPage(controller: controller),
                        TasksPage(controller: controller),
                        ProfilePage(controller: controller),
                      ],
                    ),
                  ),
                ],
              ),
              bottomNavigationBar: NavigationBar(
                selectedIndex: index,
                onDestinationSelected: (v) => setState(() => index = v),
                destinations: const [
                  NavigationDestination(icon: Icon(Icons.today), label: '今天'),
                  NavigationDestination(
                    icon: Icon(Icons.people_outline),
                    label: '客户',
                  ),
                  NavigationDestination(
                    icon: Icon(Icons.checklist),
                    label: '跟进',
                  ),
                  NavigationDestination(
                    icon: Icon(Icons.person_outline),
                    label: '我的',
                  ),
                ],
              ),
            ),
    ),
  );
}

class LoginPage extends StatefulWidget {
  final AlphaController controller;
  const LoginPage({super.key, required this.controller});
  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final server = TextEditingController(
    text: const String.fromEnvironment(
      'API_URL',
      defaultValue: 'http://10.0.2.2:8000',
    ),
  );
  final username = TextEditingController();
  final password = TextEditingController();
  bool busy = false;
  String? error;
  @override
  void dispose() {
    server.dispose();
    username.dispose();
    password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 480),
          child: ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.all(24),
            children: [
              const Text(
                '保知伴 AI',
                style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              const Text('内部 Alpha · 仅使用合成数据\n请使用管理员创建的测试账号。'),
              const SizedBox(height: 24),
              TextField(
                controller: server,
                decoration: const InputDecoration(labelText: 'Alpha 服务地址'),
                keyboardType: TextInputType.url,
              ),
              TextField(
                controller: username,
                decoration: const InputDecoration(labelText: '账号'),
                autocorrect: false,
              ),
              TextField(
                controller: password,
                decoration: const InputDecoration(labelText: '密码'),
                obscureText: true,
                autocorrect: false,
                enableSuggestions: false,
              ),
              if (error != null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(error!),
                ),
              const SizedBox(height: 20),
              FilledButton(
                onPressed: busy
                    ? null
                    : () async {
                        setState(() => busy = true);
                        try {
                          await widget.controller.login(
                            server.text.trim(),
                            username.text.trim(),
                            password.text,
                          );
                        } catch (e) {
                          if (mounted) setState(() => error = '$e');
                        } finally {
                          if (mounted) setState(() => busy = false);
                        }
                      },
                child: Text(busy ? '连接中…' : '登录'),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
