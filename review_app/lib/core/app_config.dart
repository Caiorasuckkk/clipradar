class AppConfig {
  // Android emulator can reach the host machine through 10.0.2.2.
  // On a physical phone / tunnel / cloud, build with:
  //   flutter build ... --dart-define=API_BASE_URL=https://your.url \
  //                     --dart-define=API_TOKEN=your-secret
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  // Shared secret matching the backend's API_AUTH_TOKEN. Empty = no auth (local).
  static const String apiToken = String.fromEnvironment('API_TOKEN');
}
