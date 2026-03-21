import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'app_launch_test.dart' as app_launch;
import 'feed_test.dart' as feed;
import 'bot_discovery_test.dart' as bot_discovery;
import 'chat_test.dart' as chat;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Hive App Integration Tests', () {
    app_launch.main();
    feed.main();
    bot_discovery.main();
    chat.main();
  });
}
