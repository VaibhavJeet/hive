import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:hive_observation/screens/home_screen.dart';
import 'package:hive_observation/screens/bot_discovery_screen.dart';

import 'test_app.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('App Launch and Navigation Flow', () {
    testWidgets('App launches and shows HomeScreen', (WidgetTester tester) async {
      // Arrange & Act
      await tester.pumpWidget(createTestApp());
      await pumpAndSettle(tester);

      // Assert - HomeScreen should be visible
      expect(find.byType(HomeScreen), findsOneWidget);
    });

    testWidgets('Bottom navigation bar is present with all tabs', (WidgetTester tester) async {
      // Arrange
      await tester.pumpWidget(createTestApp());
      await pumpAndSettle(tester);

      // Assert - Check for navigation items
      expect(find.text('Hive'), findsOneWidget);
      expect(find.text('Timeline'), findsOneWidget);
      expect(find.text('Beings'), findsOneWidget);
      expect(find.text('Culture'), findsOneWidget);
    });

    testWidgets('Can navigate between tabs', (WidgetTester tester) async {
      // Arrange
      await tester.pumpWidget(createTestApp());
      await pumpAndSettle(tester);

      // Act - Tap on Timeline tab
      await tapAndSettle(tester, find.text('Timeline'));

      // Assert - Should be on Timeline tab (index 1)
      // The PageView should have moved to page 1

      // Act - Tap on Beings tab
      await tapAndSettle(tester, find.text('Beings'));

      // Assert - BotDiscoveryScreen should be visible
      expect(find.byType(BotDiscoveryScreen), findsOneWidget);

      // Act - Tap on Culture tab
      await tapAndSettle(tester, find.text('Culture'));

      // Act - Navigate back to Hive
      await tapAndSettle(tester, find.text('Hive'));

      // Assert - Back to first tab
      expect(find.byType(CivilizationDashboard), findsOneWidget);
    });

    testWidgets('Hive tab shows CivilizationDashboard', (WidgetTester tester) async {
      // Arrange
      await tester.pumpWidget(createTestApp());
      await pumpAndSettle(tester);

      // Act - Make sure we're on Hive tab
      await tapAndSettle(tester, find.text('Hive'));

      // Assert
      expect(find.byType(CivilizationDashboard), findsOneWidget);
    });

    testWidgets('Navigation persists correct tab index', (WidgetTester tester) async {
      // Arrange
      await tester.pumpWidget(createTestApp());
      await pumpAndSettle(tester);

      // Act - Navigate through tabs
      await tapAndSettle(tester, find.text('Beings'));
      await tapAndSettle(tester, find.text('Timeline'));
      await tapAndSettle(tester, find.text('Culture'));
      await tapAndSettle(tester, find.text('Hive'));

      // Assert - Should be back on Hive tab with CivilizationDashboard
      expect(find.byType(CivilizationDashboard), findsOneWidget);
    });

    testWidgets('Navigation icons change state when selected', (WidgetTester tester) async {
      // Arrange
      await tester.pumpWidget(createTestApp());
      await pumpAndSettle(tester);

      // Act - Tap on Beings tab
      await tapAndSettle(tester, find.text('Beings'));

      // The active icon should be Icons.groups (filled version)
      expect(find.byIcon(Icons.groups), findsOneWidget);

      // Navigate to another tab
      await tapAndSettle(tester, find.text('Hive'));

      // The Beings icon should now be the outlined version
      expect(find.byIcon(Icons.groups_outlined), findsOneWidget);
    });
  });
}
