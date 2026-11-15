import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'api.dart';
import 'vault.dart';

typedef VaultFactory =
    Future<DraftVault> Function(String server, String account, KeyStore keys);

class AlphaController extends ChangeNotifier {
  final KeyStore keys;
  final VaultFactory vaultFactory;
  final AlphaApi Function(String) apiFactory;
  AlphaApi? api;
  DraftVault? vault;
  String username = '';
  String? notice;
  bool busy = false;
  List<Map<String, dynamic>> records = [],
      customers = [],
      tasks = [],
      drafts = [];
  AlphaController({
    KeyStore? keys,
    VaultFactory? vaultFactory,
    AlphaApi Function(String)? apiFactory,
  }) : keys = keys ?? DeviceKeys(),
       vaultFactory = vaultFactory ?? DraftVault.open,
       apiFactory = apiFactory ?? ((url) => AlphaApi(url));
  bool get loggedIn => api?.token != null && vault != null;

  Future<void> login(String server, String user, String password) async {
    final candidate = apiFactory(server);
    try {
      final result = await candidate.request(
        'POST',
        '/v1/sessions',
        body: {'username': user, 'password': password},
      );
      candidate.token = result['access_token'];
      final storage = await vaultFactory(
        candidate.base.origin,
        result['account_id'] as String,
        keys,
      );
      api?.close();
      api = candidate;
      vault = storage;
      username = user;
      await keys.write(
        'session',
        jsonEncode({
          'server': candidate.base.origin,
          'username': user,
          'account': result['account_id'],
          'token': candidate.token,
        }),
      );
      await refresh();
    } catch (_) {
      if (api != candidate) candidate.close();
      rethrow;
    }
  }

  Future<void> restore() async {
    try {
      final saved = await keys.read('session');
      if (saved == null) return;
      final data = jsonDecode(saved);
      api = apiFactory(data['server'])..token = data['token'];
      username = data['username'];
      vault = await vaultFactory(data['server'], data['account'], keys);
      await refresh();
    } catch (_) {
      notice = '无法恢复会话，请重新登录。';
      notifyListeners();
    }
  }

  Future<void> refresh() async {
    if (!loggedIn) return;
    final activeApi = api!;
    final activeVault = vault!;
    busy = true;
    notice = null;
    notifyListeners();
    try {
      final localDrafts = await activeVault.list();
      if (api != activeApi) return;
      drafts = localDrafts;
      final result = await Future.wait([
        activeApi.request('GET', '/v1/records'),
        activeApi.request('GET', '/v1/customers'),
        activeApi.request('GET', '/v1/tasks'),
      ]);
      if (api != activeApi) return;
      records = List<Map<String, dynamic>>.from(result[0]);
      customers = List<Map<String, dynamic>>.from(result[1]);
      tasks = List<Map<String, dynamic>>.from(result[2]);
    } catch (error) {
      if (api == activeApi) notice = '$error';
    } finally {
      if (api == activeApi) {
        busy = false;
        notifyListeners();
      }
    }
  }

  Future<void> upload(Map<String, dynamic> draft) async {
    final activeApi = api!;
    final activeVault = vault!;
    if (draft['type'] == 'audio') {
      await activeApi.request(
        'POST',
        '/v1/records/audio',
        audio: await activeVault.audio(draft['id']),
        query: {'client_record_id': draft['id']},
      );
    } else {
      await activeApi.request(
        'POST',
        '/v1/records',
        body: {'client_record_id': draft['id'], 'text': draft['text']},
      );
    }
    // Only delete after the server acknowledged durable persistence, not when a request starts.
    await activeVault.remove(draft['id']);
    if (api == activeApi) await refresh();
  }

  Future<void> logout() async {
    final oldApi = api;
    await keys.delete('session');
    api = null;
    vault = null;
    records = [];
    customers = [];
    tasks = [];
    drafts = [];
    notice = null;
    busy = false;
    notifyListeners();
    try {
      await oldApi
          ?.request('DELETE', '/v1/sessions/current')
          .timeout(const Duration(seconds: 3));
    } catch (_) {
      // Offline logout clears this device; server token still expires after its fixed lifetime.
    } finally {
      oldApi?.close();
    }
  }
}
