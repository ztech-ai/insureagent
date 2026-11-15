import 'dart:async';
import 'package:flutter/material.dart';
import '../../core/controller.dart';
import '../../core/widgets.dart';
import '../customers/customer_detail.dart';

class RecordDetail extends StatefulWidget {
  final AlphaController controller;
  final String id;
  const RecordDetail({super.key, required this.controller, required this.id});
  @override
  State<RecordDetail> createState() => _RecordDetailState();
}

class _RecordDetailState extends State<RecordDetail> {
  Map<String, dynamic>? row;
  String? error, customer;
  bool busy = false, customerDirty = false;
  final chosen = <String>{};
  Timer? poll;
  int polls = 0;
  @override
  void initState() {
    super.initState();
    load();
    poll = Timer.periodic(const Duration(seconds: 3), (t) {
      if (++polls > 40 || row?['data']['processing'] == 'succeeded') {
        t.cancel();
        return;
      }
      if (!busy) load();
    });
  }

  @override
  void dispose() {
    poll?.cancel();
    super.dispose();
  }

  Future<void> load() async {
    try {
      final value = await widget.controller.api!.request(
        'GET',
        '/v1/records/${widget.id}',
      );
      if (mounted)
        setState(() {
          row = Map<String, dynamic>.from(value);
          if (!customerDirty) customer = row!['related_id'];
          error = null;
        });
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  Future<void> mutate(
    String path,
    Map<String, dynamic> body, {
    String method = 'POST',
  }) async {
    if (busy) return;
    setState(() => busy = true);
    await act(context, () async {
      await widget.controller.api!.request(
        method,
        '/v1/records/${widget.id}$path',
        body: {'expected_version': row!['version'], ...body},
      );
      chosen.clear();
      customerDirty = false;
      await load();
      await widget.controller.refresh();
    });
    if (mounted) setState(() => busy = false);
  }

  Future<void> edit() async {
    final text = TextEditingController(text: row!['data']['text']);
    final changed = await showDialog<String>(
      context: context,
      builder: (dialog) => AlertDialog(
        title: const Text('更正原文'),
        content: TextField(
          controller: text,
          maxLines: 8,
          maxLength: 20000,
          decoration: const InputDecoration(helperText: '保存后旧事实撤回，重新提取并等待确认。'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialog),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialog, text.text),
            child: const Text('保存'),
          ),
        ],
      ),
    );
    text.dispose();
    if (changed != null && changed.trim().isNotEmpty)
      await mutate('', {'text': changed}, method: 'PATCH');
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('记录与事实确认'),
      actions: [
        IconButton(
          icon: const Icon(Icons.delete_outline),
          onPressed: busy || row == null
              ? null
              : () async {
                  final yes = await showDialog<bool>(
                    context: context,
                    builder: (dialog) => AlertDialog(
                      title: const Text('删除记录并撤回来源事实？'),
                      content: const Text('记录将无法访问，音频会删除，相关事实会撤回。此操作不可撤销。'),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(dialog, false),
                          child: const Text('取消'),
                        ),
                        FilledButton(
                          onPressed: () => Navigator.pop(dialog, true),
                          child: const Text('删除'),
                        ),
                      ],
                    ),
                  );
                  if (yes != true || !mounted) return;
                  await act(context, () async {
                    await widget.controller.api!.request(
                      'DELETE',
                      '/v1/records/${widget.id}',
                      body: {'expected_version': row!['version']},
                    );
                    await widget.controller.refresh();
                    if (mounted) Navigator.pop(context);
                  });
                },
        ),
        IconButton(
          onPressed: busy ? null : load,
          icon: const Icon(Icons.refresh),
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
                '已保存 · ${processingLabel(row!['data']['processing'])}',
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      row!['data']['text'].isEmpty
                          ? '语音已保存，等待转写。'
                          : row!['data']['text'],
                    ),
                    TextButton(
                      onPressed: busy ? null : edit,
                      child: const Text('更正或补充转写'),
                    ),
                    if ([
                      'failed',
                      'partial_success',
                    ].contains(row!['data']['processing']))
                      FilledButton.tonal(
                        onPressed: busy ? null : () => mutate('/retry', {}),
                        child: const Text('重试失败阶段'),
                      ),
                    const Text(
                      '候选由已配置的提取器生成，请逐项核对。',
                      style: TextStyle(fontSize: 12),
                    ),
                  ],
                ),
              ),
              section(
                '1. 确认客户归属',
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if ((row!['customer_candidates'] as List).isNotEmpty)
                      Text(
                        '匹配候选：${(row!['customer_candidates'] as List).map((c) => c['data']['name']).join('、')}',
                      ),
                    DropdownButtonFormField<String>(
                      key: ValueKey('customer-${row!['version']}'),
                      initialValue: customer,
                      decoration: const InputDecoration(
                        labelText: '选择客户；同名请进入档案核实',
                      ),
                      items: widget.controller.customers
                          .map(
                            (c) => DropdownMenuItem<String>(
                              value: c['id'],
                              child: Text(
                                '${c['data']['name']} · ${c['id'].toString().substring(0, 6)}',
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: busy
                          ? null
                          : (value) => setState(() {
                              customer = value;
                              customerDirty = true;
                            }),
                    ),
                    Wrap(
                      spacing: 8,
                      children: [
                        FilledButton(
                          onPressed: busy || customer == null
                              ? null
                              : () => mutate('/resolution', {
                                  'customer_id': customer,
                                }),
                          child: const Text('整条归属（单人）'),
                        ),
                        TextButton(
                          onPressed: busy
                              ? null
                              : () => act(context, () async {
                                  await editCustomer(
                                    context,
                                    widget.controller,
                                  );
                                  if (mounted) setState(() {});
                                }),
                          child: const Text('新建客户'),
                        ),
                        if (row!['related_id'] != null)
                          TextButton(
                            onPressed: busy
                                ? null
                                : () => mutate('/resolution', {
                                    'customer_id': null,
                                  }),
                            child: const Text('撤销归属'),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
              section(
                '2. 逐项确认事实',
                Column(
                  children: [
                    if ((row!['facts'] as List).isEmpty)
                      const Text('暂无事实候选，可先更正或补充原文。'),
                    for (final fact in row!['facts'])
                      CheckboxListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text(fact['data']['value']),
                        subtitle: Text(
                          '依据：${fact['data']['evidence']}\n归属：${fact['related_id'] ?? '未分配'} · ${fact['data']['state'] == 'confirmed' ? '已确认' : '待确认'}',
                        ),
                        value: chosen.contains(fact['id']),
                        onChanged: busy
                            ? null
                            : (value) => setState(() {
                                if (value == true) {
                                  chosen.add(fact['id']);
                                } else {
                                  chosen.remove(fact['id']);
                                }
                              }),
                      ),
                    OutlinedButton(
                      onPressed: busy || chosen.isEmpty || customer == null
                          ? null
                          : () => mutate('/segments/resolution', {
                              'fact_ids': chosen.toList(),
                              'customer_id': customer,
                            }),
                      child: const Text('把所选片段归属给上方客户'),
                    ),
                    const Text('多人记录请逐组选择片段并分配客户；同一句涉及多人时先更正原文拆句。归属后再逐项确认事实。'),
                    TextButton(
                      onPressed: busy || chosen.isEmpty
                          ? null
                          : () => mutate('/facts/retract', {
                              'fact_ids': chosen.toList(),
                            }),
                      child: const Text('撤销所选事实确认'),
                    ),
                    FilledButton(
                      onPressed: busy || chosen.isEmpty
                          ? null
                          : () => mutate('/facts/confirm', {
                              'fact_ids': chosen.toList(),
                            }),
                      child: Text('确认所选 ${chosen.length} 项'),
                    ),
                  ],
                ),
              ),
            ],
          ),
  );
}
