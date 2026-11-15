import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:insureagent_mobile/app.dart';
import 'package:insureagent_mobile/core/api.dart';
import 'package:insureagent_mobile/core/controller.dart';
import 'helpers.dart';

void main() {
  testWidgets(
    'login loads real controller state and navigation shows customers',
    (tester) async {
      final root = (await tester.runAsync(
        () => Directory.systemTemp.createTemp('alpha-widget-'),
      ))!;
      addTearDown(() => root.delete(recursive: true));
      final keys = MemoryKeys();
      final controller = AlphaController(
        keys: keys,
        vaultFactory: (server, account, keys) => testVault(root, account),
        apiFactory: (url) => AlphaApi(
          url,
          client: MockClient((request) async {
            if (request.url.path == '/v1/sessions')
              return http.Response(
                jsonEncode({
                  'account_id': 'alice',
                  'access_token': 'test-session',
                }),
                200,
                headers: {"content-type": "application/json; charset=utf-8"},
              );
            if (request.url.path == '/v1/customers')
              return http.Response(
                jsonEncode([
                  {
                    'id': 'customer-a',
                    'version': 1,
                    'data': {'name': '合成客户甲', 'notes': '测试资料', 'stage': 'lead'},
                  },
                ]),
                200,
                headers: {"content-type": "application/json; charset=utf-8"},
              );
            return http.Response('[]', 200);
          }),
        ),
      );
      await tester.pumpWidget(InsureAgentApp(controller: controller));
      expect(find.text('登录'), findsOneWidget);
      await tester.enterText(find.byType(TextField).at(1), 'alice');
      await tester.enterText(find.byType(TextField).at(2), 'alpha-passphrase');
      await tester.runAsync(() async {
        await tester.tap(find.text('登录'));
        await Future<void>.delayed(const Duration(milliseconds: 200));
      });
      await tester.pumpAndSettle();
      expect(find.text('口述记录'), findsOneWidget);
      await tester.tap(find.text('客户'));
      await tester.pumpAndSettle();
      expect(find.text('合成客户甲'), findsOneWidget);
      expect(keys.values['session'], isNot(contains('alpha-passphrase')));
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
