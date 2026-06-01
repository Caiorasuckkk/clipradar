class AppConfig {
  // Android emulator can reach the host machine through 10.0.2.2.
  // On a physical phone, run with:
  // flutter run --dart-define=API_BASE_URL=http://YOUR_PC_IP:8000
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );
}
