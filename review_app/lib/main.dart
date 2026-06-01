import 'package:flutter/material.dart';

import 'screens/review_clip_screen.dart';

void main() {
  runApp(const DarkFlowReviewApp());
}

class DarkFlowReviewApp extends StatelessWidget {
  const DarkFlowReviewApp({super.key});

  @override
  Widget build(BuildContext context) {
    const background = Color(0xFF08090E);
    const surface = Color(0xFF0F1018);
    const neon = Color(0xFF00C8F0);

    return MaterialApp(
      title: 'DarkFlow Review',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: background,
        colorScheme: const ColorScheme.dark(
          primary: neon,
          surface: surface,
          error: Color(0xFFEF4444),
        ),
        textTheme: const TextTheme(
          titleLarge: TextStyle(
            fontWeight: FontWeight.w800,
            color: Color(0xFFE8EAF0),
          ),
          titleMedium: TextStyle(
            fontWeight: FontWeight.w700,
            color: Color(0xFFE8EAF0),
          ),
          bodyMedium: TextStyle(color: Color(0xFFC0C4D6)),
          bodySmall: TextStyle(color: Color(0xFF8C93A6)),
        ),
      ),
      home: const ReviewClipScreen(),
    );
  }
}
