import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:insureagent_mobile/core/api.dart';
import 'package:insureagent_mobile/core/controller.dart';
import 'helpers.dart';

void main() {
  test(
    'upload retry keeps stable client id and removes draft only after durable acknowledgement',
    () async {
      final root = await Directory.systemTemp.createTemp('alpha-controller-');
      addTearDown(() => root.delete(recursive: true));
      final vault = await testVault(root, 'alice');
      final keys = MemoryKeys();
      var offline = true;
      final submitted = <String>[];
      final client = MockClient((request) async {
        if (request.url.path == '/v1/records' && request.method == 'POST') {
          submitted.add(jsonDecode(request.body)['client_record_id']);
          if (offline) throw const SocketException('offline');
          return http.Response('{}', 201);
        }
        return http.Response('[]', 200);
      });
      final controller = AlphaController(keys: keys)
        ..vault = vault
        ..api = (AlphaApi('http://localhost:8000', client: client)
          ..token = 'test-session');
      final id = await vault.create(text: 'synthetic text');
      final draft = (await vault.list()).single;
      await expectLater(controller.upload(draft), throwsA(isA<ApiFailure>()));
      expect((await vault.list()).single['id'], id);
      offline = false;
      await controller.upload(draft);
      expect(submitted, [id, id]);
      expect(await vault.list(), isEmpty);
      await controller.logout();
      expect(controller.loggedIn, isFalse);
      expect(controller.records, isEmpty);
    },
  );
  test(
    'server error does not include raw response in the user message',
    () async {
      final api = AlphaApi(
        'http://localhost',
        client: MockClient(
          (_) async => http.Response('{"detail":"version_conflict"}', 409),
        ),
      );
      await expectLater(
        api.request('GET', '/v1/records'),
        throwsA(isA<ApiFailure>().having((e) => e.status, 'status', 409)),
      );
    },
  );
  test('late account response cannot repopulate lists after logout', () async {
    final root = await Directory.systemTemp.createTemp('alpha-race-');
    addTearDown(() => root.delete(recursive: true));
    final entered = Completer<void>();
    final delayed = Completer<http.Response>();
    final client = MockClient((request) async {
      if (request.url.path == '/v1/records') {
        entered.complete();
        return delayed.future;
      }
      return http.Response('[]', 200);
    });
    final controller = AlphaController(keys: MemoryKeys())
      ..vault = await testVault(root, 'alice')
      ..api = (AlphaApi('http://localhost', client: client)
        ..token = 'alice-token');
    final loading = controller.refresh();
    await entered.future;
    await controller.logout();
    delayed.complete(http.Response('[{"id":"private-alice-record"}]', 200));
    await loading;
    expect(controller.loggedIn, isFalse);
    expect(controller.records, isEmpty);
  });
  test('malformed and sensitive error responses are not echoed', () async {
    for (final body in [
      '<html>private-contact</html>',
      '{"detail":"private contact 13800138000"}',
    ]) {
      final api = AlphaApi(
        'http://localhost',
        client: MockClient((_) async => http.Response(body, 500)),
      );
      try {
        await api.request('GET', '/v1/records');
        fail('must reject');
      } on ApiFailure catch (error) {
        expect('$error', isNot(contains('private')));
        expect('$error', isNot(contains('13800138000')));
      }
    }
  });
}
