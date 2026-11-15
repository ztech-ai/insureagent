import 'package:uuid/uuid.dart';
import 'package:flutter/material.dart';
import '../../core/controller.dart';
import '../../core/widgets.dart';
import '../confirmation/record_detail.dart';

Future<void> editCustomer(
  BuildContext context,
  AlphaController c, {
  Map<String, dynamic>? row,
}) async {
  final requestId = const Uuid().v4();
  final name = TextEditingController(text: row?['data']['name'] ?? '');
  final notes = TextEditingController(text: row?['data']['notes'] ?? '');
  var stage = row?['data']['stage'] ?? 'lead';
  var saving = false;
  await showDialog<void>(
    context: context,
    builder: (dialog) => StatefulBuilder(
      builder: (context, setState) => AlertDialog(
        title: Text(row == null ? '新建客户' : '编辑客户'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: name,
                maxLength: 100,
                decoration: const InputDecoration(labelText: '姓名或代称'),
              ),
              TextField(
                controller: notes,
                maxLength: 4000,
                maxLines: 3,
                decoration: const InputDecoration(labelText: '备注'),
              ),
              DropdownButtonFormField<String>(
                initialValue: stage,
                items: const [
                  DropdownMenuItem(value: 'lead', child: Text('线索')),
                  DropdownMenuItem(value: 'contacted', child: Text('已联系')),
                  DropdownMenuItem(value: 'needs', child: Text('需求核实')),
                  DropdownMenuItem(value: 'serving', child: Text('持续服务')),
                ],
                onChanged: (v) => stage = v!,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: saving ? null : () => Navigator.pop(dialog),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: saving
                ? null
                : () async {
                    if (name.text.trim().isEmpty) return;
                    setState(() => saving = true);
                    await act(context, () async {
                      await c.api!.request(
                        row == null ? 'POST' : 'PATCH',
                        row == null
                            ? '/v1/customers'
                            : '/v1/customers/${row['id']}',
                        body: {
                          if (row == null) 'client_request_id': requestId,
                          'name': name.text.trim(),
                          'notes': notes.text,
                          'stage': stage,
                          'tags': row?['data']['tags'] ?? [],
                          if (row != null) 'expected_version': row['version'],
                        },
                      );
                      await c.refresh();
                      if (dialog.mounted) Navigator.pop(dialog);
                    });
                    if (context.mounted) setState(() => saving = false);
                  },
            child: Text(saving ? '保存中' : '保存'),
          ),
        ],
      ),
    ),
  );
  name.dispose();
  notes.dispose();
}

class CustomerDetail extends StatefulWidget {
  final AlphaController controller;
  final String id;
  const CustomerDetail({super.key, required this.controller, required this.id});
  @override
  State<CustomerDetail> createState() => _CustomerDetailState();
}

class _CustomerDetailState extends State<CustomerDetail> {
  Map<String, dynamic>? row;
  String? error;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final value = await widget.controller.api!.request(
        'GET',
        '/v1/customers/${widget.id}',
      );
      if (mounted)
        setState(() {
          row = Map<String, dynamic>.from(value);
          error = null;
        });
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(row?['data']['name'] ?? '客户档案'),
      actions: [
        IconButton(onPressed: load, icon: const Icon(Icons.refresh)),
        if (row != null)
          IconButton(
            onPressed: () => act(context, () async {
              await editCustomer(context, widget.controller, row: row);
              await load();
            }),
            icon: const Icon(Icons.edit),
          ),
      ],
    ),
    body: error != null
        ? Center(child: Text(error!))
        : row == null
        ? const Center(child: CircularProgressIndicator())
        : ListView(
            padding: const EdgeInsets.all(16),
            children: [
              section(
                '基本资料',
                Text('${row!['data']['notes']}\n阶段：${row!['data']['stage']}'),
              ),
              section(
                '已确认事实',
                Column(
                  children: [
                    if ((row!['facts'] as List).isEmpty) const Text('尚无已确认事实'),
                    for (final fact in row!['facts'])
                      ListTile(
                        title: Text(fact['data']['value']),
                        subtitle: Text('依据：${fact['data']['evidence']}'),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => RecordDetail(
                              controller: widget.controller,
                              id: fact['source_id'],
                            ),
                          ),
                        ).then((_) => load()),
                      ),
                  ],
                ),
              ),
              section(
                '接触时间线',
                Column(
                  children: [
                    for (final record in row!['records'])
                      ListTile(
                        title: Text(
                          record['data']['text'].isEmpty
                              ? '语音记录'
                              : record['data']['text'],
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        subtitle: Text(localTime(record['created_at'])),
                        onTap: () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => RecordDetail(
                              controller: widget.controller,
                              id: record['id'],
                            ),
                          ),
                        ).then((_) => load()),
                      ),
                  ],
                ),
              ),
            ],
          ),
  );
}
