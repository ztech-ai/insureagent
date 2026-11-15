import 'package:flutter/material.dart';
import '../../core/controller.dart';
import '../../core/widgets.dart';
import '../recording/editor.dart';
import '../confirmation/record_detail.dart';

class TodayPage extends StatefulWidget {
  final AlphaController controller;
  const TodayPage({super.key, required this.controller});
  @override
  State<TodayPage> createState() => _TodayPageState();
}

class _TodayPageState extends State<TodayPage> {
  String query = '';
  final uploading = <String>{};
  void editor({bool audio = false, Map<String, dynamic>? draft}) =>
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => RecordEditor(
            controller: widget.controller,
            audio: audio,
            draft: draft,
          ),
        ),
      ).then((_) => widget.controller.refresh());
  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: widget.controller.refresh,
    child: ListView(
      padding: const EdgeInsets.all(16),
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        const Text(
          '把今天的联系，记清楚',
          style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 12,
          children: [
            FilledButton.icon(
              onPressed: () => editor(audio: true),
              icon: const Icon(Icons.mic),
              label: const Text('口述记录'),
            ),
            OutlinedButton.icon(
              onPressed: () => editor(),
              icon: const Icon(Icons.edit_note),
              label: const Text('文字记录'),
            ),
          ],
        ),
        const SizedBox(height: 20),
        if (widget.controller.drafts.isNotEmpty)
          section(
            '本机加密草稿',
            Column(
              children: [
                for (final draft in widget.controller.drafts)
                  ListTile(
                    title: Text(
                      draft['type'] == 'audio' ? '语音草稿（含中断片段）' : draft['text'],
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: Text('尚未上传 · ${localTime(draft['created_at'])}'),
                    onTap: draft['type'] == 'text'
                        ? () => editor(draft: draft)
                        : null,
                    trailing: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        IconButton(
                          tooltip: '上传',
                          onPressed: uploading.contains(draft['id'])
                              ? null
                              : () async {
                                  if (draft['type'] == 'audio') {
                                    final accepted = await showDialog<bool>(
                                      context: context,
                                      builder: (dialog) => AlertDialog(
                                        title: const Text('恢复并上传语音片段？'),
                                        content: const Text(
                                          '中断前的录音片段会上传，末尾可能不完整。转写后请核对并补充。',
                                        ),
                                        actions: [
                                          TextButton(
                                            onPressed: () =>
                                                Navigator.pop(dialog, false),
                                            child: const Text('取消'),
                                          ),
                                          FilledButton(
                                            onPressed: () =>
                                                Navigator.pop(dialog, true),
                                            child: const Text('上传片段'),
                                          ),
                                        ],
                                      ),
                                    );
                                    if (accepted != true || !mounted) return;
                                  }
                                  setState(() => uploading.add(draft['id']));
                                  await act(
                                    context,
                                    () => widget.controller.upload(draft),
                                  );
                                  if (mounted)
                                    setState(
                                      () => uploading.remove(draft['id']),
                                    );
                                },
                          icon: const Icon(Icons.cloud_upload_outlined),
                        ),
                        IconButton(
                          tooltip: '删除本机草稿',
                          onPressed: uploading.contains(draft['id'])
                              ? null
                              : () async {
                                  final yes = await showDialog<bool>(
                                    context: context,
                                    builder: (dialog) => AlertDialog(
                                      title: const Text('删除此本机草稿？'),
                                      content: const Text('草稿尚未上传，删除后无法恢复。'),
                                      actions: [
                                        TextButton(
                                          onPressed: () =>
                                              Navigator.pop(dialog, false),
                                          child: const Text('取消'),
                                        ),
                                        TextButton(
                                          onPressed: () =>
                                              Navigator.pop(dialog, true),
                                          child: const Text('删除'),
                                        ),
                                      ],
                                    ),
                                  );
                                  if (yes == true && context.mounted)
                                    await act(context, () async {
                                      await widget.controller.vault!.remove(
                                        draft['id'],
                                      );
                                      await widget.controller.refresh();
                                    });
                                },
                          icon: const Icon(Icons.delete_outline),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        TextField(
          decoration: const InputDecoration(
            labelText: '搜索已保存记录',
            prefixIcon: Icon(Icons.search),
          ),
          onChanged: (v) => setState(() => query = v),
        ),
        for (final row in widget.controller.records.where(
          (r) => r['data']['text'].toString().contains(query),
        ))
          Card(
            child: ListTile(
              title: Text(
                row['data']['text'].isEmpty
                    ? '语音记录 · 等待转写'
                    : row['data']['text'],
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              subtitle: Text(
                '${localTime(row['created_at'])} · ${processingLabel(row['data']['processing'])}',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => RecordDetail(
                    controller: widget.controller,
                    id: row['id'],
                  ),
                ),
              ).then((_) => widget.controller.refresh()),
            ),
          ),
        if (widget.controller.records.isEmpty)
          const Padding(
            padding: EdgeInsets.all(24),
            child: Text('还没有云端记录。先记录一次接触，再核对客户与事实。'),
          ),
      ],
    ),
  );
}
