import 'package:flutter_test/flutter_test.dart';
import 'package:insureagent_mobile/app.dart';

void main() {
  testWidgets('navigation preserves bootstrap scope', (tester) async {
    await tester.pumpWidget(const InsureAgentApp());
    expect(find.text('记录入口尚未接入录音和云端服务'), findsOneWidget);
    await tester.tap(find.text('客户'));
    await tester.pumpAndSettle();
    expect(find.text('客户档案模块待实现'), findsOneWidget);
  });
}
