import 'dart:async';
import 'package:flutter/material.dart';
import 'package:record/record.dart';
import '../../core/controller.dart';

class RecordEditor extends StatefulWidget {
  final AlphaController controller;
  final bool audio;
  final Map<String, dynamic>? draft;
  const RecordEditor({
    super.key,
    required this.controller,
    this.audio = false,
    this.draft,
  });
  @override
  State<RecordEditor> createState() => _RecordEditorState();
}

class _RecordEditorState extends State<RecordEditor>
    with WidgetsBindingObserver {
  final text = TextEditingController();
  final recorder = AudioRecorder();
  String? id;
  String? error;
  bool recording = false, paused = false, busy = false;
  bool storageFailed = false;
  int bytes = 0, sequence = 0;
  StreamSubscription? subscription;
  Future<void> pending = Future.value();
  Future<void>? initializing;
  Timer? timer;
  int elapsed = 0;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    id = widget.draft?['id'];
    text.text = widget.draft?['text'] ?? '';
    if (!widget.audio) text.addListener(() => queueSave());
  }

  Future<void> ensureDraft() async {
    if (id != null) return;
    initializing ??= () async {
      id = await widget.controller.vault!.create(
        type: widget.audio ? 'audio' : 'text',
        text: text.text,
      );
    }();
    await initializing;
  }

  void queueSave() {
    final value = text.text;
    pending = pending
        .then((_) async {
          await ensureDraft();
          await widget.controller.vault!.save({
            'id': id,
            'type': 'text',
            'text': value,
            'created_at':
                widget.draft?['created_at'] ?? DateTime.now().toIso8601String(),
          });
        })
        .catchError((Object e) {
          storageFailed = true;
          if (mounted) setState(() => error = '草稿保存失败：$e');
        });
  }

  Future<void> start() async {
    if (busy || recording) return;
    setState(() => busy = true);
    try {
      if (!await recorder.hasPermission())
        throw StateError('未获得麦克风权限，请返回选择文字记录。');
      await ensureDraft();
      final stream = await recorder.startStream(
        const RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: 16000,
          numChannels: 1,
          streamBufferSize: 16000,
        ),
      );
      subscription = stream.listen(
        (chunk) {
          if (bytes + chunk.length > 16000 * 2 * 600) {
            stop();
            return;
          }
          bytes += chunk.length;
          final index = sequence++;
          pending = pending
              .then(
                (_) => widget.controller.vault!.appendAudio(id!, index, chunk),
              )
              .catchError((Object e) {
                storageFailed = true;
                if (mounted) setState(() => error = '录音保存失败：$e');
                stop();
              });
        },
        onError: (Object e) {
          if (mounted) setState(() => error = '录音中断，已保存片段可恢复。');
          stop();
        },
        onDone: () {
          timer?.cancel();
          if (mounted) setState(() => recording = false);
        },
      );
      timer = Timer.periodic(const Duration(seconds: 1), (t) {
        if (!paused && mounted) setState(() => elapsed++);
        if (elapsed >= 600) stop();
      });
      if (mounted)
        setState(() {
          recording = true;
          error = null;
        });
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> stop() async {
    if (!recording) return;
    recording = false;
    timer?.cancel();
    await recorder.stop();
    await subscription?.cancel();
    await pending;
    if (mounted) setState(() {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused) {
      stop();
      if (mounted) setState(() => error = '切换后台已停止录音，已保存片段保留在本机。');
    }
  }

  Future<void> save(bool upload) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      await stop();
      if (!widget.audio) {
        if (text.text.trim().isEmpty) throw StateError('请输入记录内容');
        queueSave();
      }
      await pending;
      if (storageFailed) throw StateError('本机写入失败，请保留草稿并检查存储空间，不能上传不完整记录。');
      if (id == null) throw StateError('请先录音或输入文字');
      if (widget.audio)
        await widget.controller.vault!.audio(id!); // Validate before upload.
      await widget.controller.refresh();
      if (upload) {
        final draft = (await widget.controller.vault!.list()).firstWhere(
          (d) => d['id'] == id,
        );
        await widget.controller.upload(draft);
      }
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    timer?.cancel();
    subscription?.cancel();
    recorder.dispose();
    text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !recording && !busy,
    child: Scaffold(
      appBar: AppBar(title: Text(widget.audio ? '口述记录' : '文字记录')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Text('仅用于 Alpha 合成场景。上传前内容加密保存在本机；请勿录入真实客户资料。'),
          const SizedBox(height: 20),
          if (widget.audio) ...[
            Center(
              child: Text(
                '${elapsed ~/ 60}:${(elapsed % 60).toString().padLeft(2, '0')}',
                style: const TextStyle(fontSize: 48),
              ),
            ),
            if (!recording && sequence == 0)
              FilledButton.icon(
                onPressed: busy ? null : start,
                icon: const Icon(Icons.mic),
                label: const Text('开始录音'),
              ),
            if (recording)
              Wrap(
                spacing: 12,
                children: [
                  OutlinedButton(
                    onPressed: () async {
                      if (paused) {
                        await recorder.resume();
                      } else {
                        await recorder.pause();
                      }
                      if (mounted) setState(() => paused = !paused);
                    },
                    child: Text(paused ? '继续' : '暂停'),
                  ),
                  FilledButton(onPressed: stop, child: const Text('结束录音')),
                ],
              ),
            const Text('最长十分钟；切换后台会停止录音并保留已加密片段。'),
          ] else
            TextField(
              controller: text,
              minLines: 8,
              maxLines: 16,
              maxLength: 20000,
              decoration: const InputDecoration(
                hintText: '例如：客户陈敏，今天讨论家庭保障，下周继续核实。',
                border: OutlineInputBorder(),
              ),
            ),
          if (error != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(
                error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          const SizedBox(height: 20),
          FilledButton(
            onPressed: busy ? null : () => save(true),
            child: Text(busy ? '保存中…' : '保存并上传'),
          ),
          OutlinedButton(
            onPressed: busy ? null : () => save(false),
            child: const Text('仅保存加密草稿'),
          ),
        ],
      ),
    ),
  );
}
