import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:cryptography/cryptography.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';

abstract class KeyStore {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> delete(String key);
}

class DeviceKeys implements KeyStore {
  final FlutterSecureStorage storage = const FlutterSecureStorage();
  @override
  Future<String?> read(String key) => storage.read(key: key);
  @override
  Future<void> write(String key, String value) =>
      storage.write(key: key, value: value);
  @override
  Future<void> delete(String key) => storage.delete(key: key);
}

class DraftVault {
  final Directory directory;
  final SecretKey key;
  final String scope;
  final AesGcm cipher = AesGcm.with256bits();
  DraftVault(this.directory, this.key, this.scope);

  static Future<DraftVault> open(
    String server,
    String account,
    KeyStore keys,
  ) async {
    final digest = await Sha256().hash(utf8.encode('$server/$account'));
    final scope = digest.bytes
        .map((b) => b.toRadixString(16).padLeft(2, '0'))
        .join();
    var stored = await keys.read('draft-key-$scope');
    if (stored == null) {
      stored = base64Encode(
        await (await AesGcm.with256bits().newSecretKey()).extractBytes(),
      );
      await keys.write('draft-key-$scope', stored);
    }
    final root = await getApplicationSupportDirectory();
    final directory = Directory('${root.path}/drafts/$scope');
    await directory.create(recursive: true);
    return DraftVault(directory, SecretKey(base64Decode(stored)), scope);
  }

  String _safe(String value) {
    if (!RegExp(r'^[a-zA-Z0-9_.-]+$').hasMatch(value) || value.contains('..')) {
      throw ArgumentError('invalid local identifier');
    }
    return value;
  }

  Future<void> _write(String name, List<int> bytes) async {
    final box = await cipher.encrypt(
      bytes,
      secretKey: key,
      aad: utf8.encode('$scope/$name'),
    );
    final temp = File('${directory.path}/${_safe(name)}.tmp');
    await temp.writeAsBytes(box.concatenation(), flush: true);
    await temp.rename('${directory.path}/$name');
  }

  Future<Uint8List> _read(String name) async {
    final raw = await File('${directory.path}/${_safe(name)}').readAsBytes();
    final box = SecretBox.fromConcatenation(
      raw,
      nonceLength: 12,
      macLength: 16,
    );
    return Uint8List.fromList(
      await cipher.decrypt(
        box,
        secretKey: key,
        aad: utf8.encode('$scope/$name'),
      ),
    );
  }

  Future<String> create({String text = '', String type = 'text'}) async {
    final id = const Uuid().v4();
    await save({
      'id': id,
      'type': type,
      'text': text,
      'created_at': DateTime.now().toIso8601String(),
    });
    return id;
  }

  Future<void> save(Map<String, dynamic> draft) => _write(
    '${_safe(draft['id'] as String)}.json.enc',
    utf8.encode(jsonEncode(draft)),
  );

  Future<List<Map<String, dynamic>>> list() async {
    final drafts = <Map<String, dynamic>>[];
    await for (final file in directory.list()) {
      if (file is File && file.path.endsWith('.json.enc')) {
        final name = file.uri.pathSegments.last;
        final draft =
            jsonDecode(utf8.decode(await _read(name))) as Map<String, dynamic>;
        drafts.add(draft);
      }
    }
    drafts.sort(
      (a, b) =>
          (b['created_at'] as String).compareTo(a['created_at'] as String),
    );
    return drafts;
  }

  Future<void> appendAudio(String id, int sequence, Uint8List pcm) => _write(
    '${_safe(id)}.${sequence.toString().padLeft(6, '0')}.pcm.enc',
    pcm,
  );

  Future<Uint8List> audio(String id) async {
    _safe(id);
    final files = await directory
        .list()
        .where(
          (file) =>
              file is File &&
              file.uri.pathSegments.last.startsWith('${_safe(id)}.') &&
              file.path.endsWith('.pcm.enc'),
        )
        .toList();
    files.sort((a, b) => a.path.compareTo(b.path));
    final builder = BytesBuilder(copy: false);
    var expected = 0;
    for (final file in files) {
      final name = file.uri.pathSegments.last;
      if (name != '$id.${expected.toString().padLeft(6, "0")}.pcm.enc') {
        throw StateError("录音片段缺失，不能上传不完整内容");
      }
      expected++;
      builder.add(await _read(file.uri.pathSegments.last));
      if (builder.length > 16000 * 2 * 600) throw StateError('录音超过十分钟');
    }
    final pcm = builder.takeBytes();
    if (pcm.length < 3200 || pcm.length.isOdd)
      throw StateError('录音太短或不完整，请改用文字');
    final header = ByteData(44);
    void label(int offset, String value) {
      for (var i = 0; i < value.length; i++) {
        header.setUint8(offset + i, value.codeUnitAt(i));
      }
    }

    label(0, 'RIFF');
    header.setUint32(4, pcm.length + 36, Endian.little);
    label(8, 'WAVE');
    label(12, 'fmt ');
    header.setUint32(16, 16, Endian.little);
    header.setUint16(20, 1, Endian.little);
    header.setUint16(22, 1, Endian.little);
    header.setUint32(24, 16000, Endian.little);
    header.setUint32(28, 32000, Endian.little);
    header.setUint16(32, 2, Endian.little);
    header.setUint16(34, 16, Endian.little);
    label(36, 'data');
    header.setUint32(40, pcm.length, Endian.little);
    return (BytesBuilder()
          ..add(header.buffer.asUint8List())
          ..add(pcm))
        .takeBytes();
  }

  Future<void> remove(String id) async {
    _safe(id);
    await for (final file in directory.list()) {
      if (file is File &&
          file.uri.pathSegments.last.startsWith('${_safe(id)}.'))
        await file.delete();
    }
  }
}
