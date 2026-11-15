import 'package:flutter/material.dart';

Future<void> act(BuildContext context, Future<void> Function() work) async {
  try {
    await work();
  } catch (error) {
    if (context.mounted)
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('$error')));
  }
}

String localTime(dynamic value) {
  final date = DateTime.tryParse('$value')?.toLocal();
  if (date == null) return '';
  return '${date.month}/${date.day} ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
}

String processingLabel(dynamic value) => switch (value) {
  'queued' => '等待处理',
  'running' => '处理中',
  'succeeded' => '处理完成，待核对',
  'failed' => '处理失败，可重试或手动校正',
  'partial_success' => '转写已完成，提取待重试',
  _ => '$value',
};

Widget section(String title, Widget child) => Card(
  child: Padding(
    padding: const EdgeInsets.all(16),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 12),
        child,
      ],
    ),
  ),
);
