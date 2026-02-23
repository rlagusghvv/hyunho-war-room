import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kid_econ_mvp/main.dart';

void main() {
  testWidgets('머니탐험대 앱 부팅', (WidgetTester tester) async {
    await tester.pumpWidget(const MoneyExplorerApp());
    expect(find.byType(MaterialApp), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });
}
