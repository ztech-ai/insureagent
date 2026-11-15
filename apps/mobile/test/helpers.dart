import 'dart:io';
import 'package:cryptography/cryptography.dart';
import 'package:insureagent_mobile/core/vault.dart';

class MemoryKeys implements KeyStore {
  final values = <String, String>{};
  @override
  Future<String?> read(String key) async => values[key];
  @override
  Future<void> write(String key, String value) async {
    values[key] = value;
  }

  @override
  Future<void> delete(String key) async {
    values.remove(key);
  }
}

Future<DraftVault> testVault(Directory root, String account) async {
  final directory = Directory('${root.path}/$account');
  await directory.create(recursive: true);
  return DraftVault(
    directory,
    SecretKey(List.filled(32, account == 'alice' ? 1 : 2)),
    account,
  );
}
