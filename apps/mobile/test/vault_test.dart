import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:cryptography/cryptography.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:insureagent_mobile/core/vault.dart';
import 'helpers.dart';

void main() {
  late Directory root;
  setUp(() async {
    root = await Directory.systemTemp.createTemp('alpha-vault-');
  });
  tearDown(() async {
    await root.delete(recursive: true);
  });
  test(
    'draft ciphertext survives reopen and rejects another account key',
    () async {
      final vault = await testVault(root, 'alice');
      final id = await vault.create(text: 'synthetic-contact-13800138000');
      final file = File('${vault.directory.path}/$id.json.enc');
      expect(
        utf8.decode(await file.readAsBytes(), allowMalformed: true),
        isNot(contains('13800138000')),
      );
      final reopened = await testVault(root, 'alice');
      expect(
        (await reopened.list()).single['text'],
        'synthetic-contact-13800138000',
      );
      final wrong = DraftVault(
        vault.directory,
        SecretKey(List.filled(32, 2)),
        'bob',
      );
      await expectLater(
        wrong.list(),
        throwsA(isA<SecretBoxAuthenticationError>()),
      );
      final raw = await file.readAsBytes();
      raw[20] ^= 1;
      await file.writeAsBytes(raw);
      await expectLater(
        reopened.list(),
        throwsA(isA<SecretBoxAuthenticationError>()),
      );
    },
  );
  test(
    'encrypted audio chunks recover in order and deletion removes all chunks',
    () async {
      final vault = await testVault(root, 'alice');
      final id = await vault.create(type: 'audio');
      await vault.appendAudio(id, 1, Uint8List.fromList(List.filled(1600, 2)));
      await vault.appendAudio(id, 0, Uint8List.fromList(List.filled(1600, 1)));
      final wav = await vault.audio(id);
      expect(utf8.decode(wav.sublist(0, 4)), 'RIFF');
      expect(wav.length, 3244);
      expect(wav[44], 1);
      expect(wav[1644], 2);
      expect(ByteData.sublistView(wav).getUint32(24, Endian.little), 16000);
      await vault.remove(id);
      expect(await vault.list(), isEmpty);
      expect(await vault.directory.list().toList(), isEmpty);
    },
  );
  test('path traversal identifiers are rejected', () async {
    final vault = await testVault(root, 'alice');
    await expectLater(vault.remove('../outside'), throwsArgumentError);
  });
  test('missing audio fragment cannot be silently joined', () async {
    final vault = await testVault(root, 'alice');
    final id = await vault.create(type: 'audio');
    await vault.appendAudio(id, 0, Uint8List(3200));
    await vault.appendAudio(id, 2, Uint8List(3200));
    await expectLater(vault.audio(id), throwsStateError);
  });
}
