import 'package:uuid/uuid.dart';
import 'package:flutter/material.dart';
import '../../core/controller.dart';
import '../../core/widgets.dart';

class TasksPage extends StatelessWidget {
  final AlphaController controller;
  const TasksPage({super.key, required this.controller});
  Future<void> edit(BuildContext context, {Map<String, dynamic>? row}) async {
    final requestId = const Uuid().v4();
    final title = TextEditingController(text: row?['data']['title'] ?? '');
    final outcome = TextEditingController(text: row?['data']['outcome'] ?? '');
    String? customer = row?['related_id'];
    var due =
        DateTime.tryParse(row?['data']['due_at'] ?? '')?.toLocal() ??
        DateTime.now().add(const Duration(days: 1));
    var status = row?['data']['status'] ?? 'open';
    var busy = false;
    await showDialog<void>(
      context: context,
      builder: (dialog) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          title: Text(row == null ? '新建手动跟进' : '更新跟进'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (row == null)
                  DropdownButtonFormField<String>(
                    initialValue: customer,
                    decoration: const InputDecoration(labelText: '客户'),
                    items: controller.customers
                        .map(
                          (c) => DropdownMenuItem<String>(
                            value: c['id'],
                            child: Text(c['data']['name']),
                          ),
                        )
                        .toList(),
                    onChanged: (v) => customer = v,
                  ),
                TextField(
                  controller: title,
                  maxLength: 200,
                  readOnly: row != null,
                  decoration: const InputDecoration(labelText: '跟进事项'),
                ),
                TextButton(
                  onPressed: () async {
                    final date = await showDatePicker(
                      context: context,
                      initialDate: due,
                      firstDate: DateTime(2020),
                      lastDate: DateTime(2040),
                    );
                    if (date == null || !context.mounted) return;
                    final time = await showTimePicker(
                      context: context,
                      initialTime: TimeOfDay.fromDateTime(due),
                    );
                    if (time != null)
                      setState(
                        () => due = DateTime(
                          date.year,
                          date.month,
                          date.day,
                          time.hour,
                          time.minute,
                        ),
                      );
                  },
                  child: Text('时间：${localTime(due.toIso8601String())}'),
                ),
                if (row != null) ...[
                  DropdownButtonFormField<String>(
                    initialValue: status,
                    items: const [
                      DropdownMenuItem(value: 'open', child: Text('待跟进／延期')),
                      DropdownMenuItem(value: 'completed', child: Text('已完成')),
                      DropdownMenuItem(value: 'cancelled', child: Text('已取消')),
                    ],
                    onChanged: (v) => status = v!,
                  ),
                  TextField(
                    controller: outcome,
                    maxLength: 1000,
                    maxLines: 3,
                    decoration: const InputDecoration(labelText: '实际联系结果'),
                  ),
                ],
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: busy ? null : () => Navigator.pop(dialog),
              child: const Text('取消'),
            ),
            FilledButton(
              onPressed: busy
                  ? null
                  : () async {
                      if (customer == null || title.text.trim().isEmpty) return;
                      setState(() => busy = true);
                      await act(context, () async {
                        await controller.api!.request(
                          row == null ? 'POST' : 'PATCH',
                          row == null ? '/v1/tasks' : '/v1/tasks/${row['id']}',
                          body: row == null
                              ? {
                                  'client_request_id': requestId,
                                  'customer_id': customer,
                                  'title': title.text.trim(),
                                  'due_at': due.toUtc().toIso8601String(),
                                }
                              : {
                                  'expected_version': row['version'],
                                  'status': status,
                                  'due_at': due.toUtc().toIso8601String(),
                                  'outcome': outcome.text,
                                },
                        );
                        await controller.refresh();
                        if (dialog.mounted) Navigator.pop(dialog);
                      });
                      if (context.mounted) setState(() => busy = false);
                    },
              child: const Text('保存'),
            ),
          ],
        ),
      ),
    );
    title.dispose();
    outcome.dispose();
  }

  @override
  Widget build(BuildContext context) => Column(
    children: [
      Padding(
        padding: const EdgeInsets.all(16),
        child: FilledButton.icon(
          onPressed: () => edit(context),
          icon: const Icon(Icons.add),
          label: const Text('新建手动跟进'),
        ),
      ),
      Expanded(
        child: RefreshIndicator(
          onRefresh: controller.refresh,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            children: [
              if (controller.tasks.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(24),
                  child: Text('手动跟进免费可用；完成任务不会自动标记成交。'),
                ),
              for (final task in controller.tasks)
                ListTile(
                  leading: Icon(
                    task['data']['status'] == 'completed'
                        ? Icons.check_circle
                        : Icons.event,
                  ),
                  title: Text(task['data']['title']),
                  subtitle: Text(
                    '${localTime(task['data']['due_at'])} · ${task['data']['status']}\n${task['data']['outcome']}',
                  ),
                  onTap: () => edit(context, row: task),
                ),
            ],
          ),
        ),
      ),
    ],
  );
}
