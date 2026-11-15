import 'package:flutter/material.dart';
import 'features/today/today_page.dart';
import 'features/customers/customers_page.dart';
import 'features/tasks/tasks_page.dart';
import 'features/profile/profile_page.dart';

class InsureAgentApp extends StatefulWidget {
  const InsureAgentApp({super.key});
  @override
  State<InsureAgentApp> createState() => _InsureAgentAppState();
}

class _InsureAgentAppState extends State<InsureAgentApp> {
  int index = 0;
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: '保知伴 AI',
    theme: ThemeData(
      colorSchemeSeed: const Color(0xff22634b),
      useMaterial3: true,
    ),
    home: Scaffold(
      appBar: AppBar(title: const Text('保知伴 AI · 开发骨架')),
      body: IndexedStack(
        index: index,
        children: const [
          TodayPage(),
          CustomersPage(),
          TasksPage(),
          ProfilePage(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (value) => setState(() => index = value),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.today), label: '今天'),
          NavigationDestination(icon: Icon(Icons.people_outline), label: '客户'),
          NavigationDestination(icon: Icon(Icons.checklist), label: '跟进'),
          NavigationDestination(icon: Icon(Icons.person_outline), label: '我的'),
        ],
      ),
    ),
  );
}
