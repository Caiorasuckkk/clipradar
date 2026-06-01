import 'package:flutter_test/flutter_test.dart';
import 'package:review_app/main.dart';

void main() {
  testWidgets('DarkFlow Review app boots', (tester) async {
    await tester.pumpWidget(const DarkFlowReviewApp());
    expect(find.byType(DarkFlowReviewApp), findsOneWidget);
  });
}
