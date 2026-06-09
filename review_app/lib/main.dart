import 'package:flutter/material.dart';

import 'screens/cuts_screen.dart';
import 'screens/home_screen.dart';
import 'screens/more_screen.dart';
import 'theme/app_colors.dart';
import 'widgets/df_bottom_nav.dart';

void main() {
  runApp(const DarkFlowReviewApp());
}

class DarkFlowReviewApp extends StatelessWidget {
  const DarkFlowReviewApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'DarkFlow Review',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: AppColors.background,
        colorScheme: const ColorScheme.dark(
          primary: AppColors.cyan,
          surface: AppColors.surface,
          error: AppColors.danger,
        ),
        textTheme: const TextTheme(
          titleLarge: TextStyle(
            fontWeight: FontWeight.w800,
            color: AppColors.text,
          ),
          titleMedium: TextStyle(
            fontWeight: FontWeight.w700,
            color: AppColors.text,
          ),
          bodyMedium: TextStyle(color: Color(0xFFC0C4D6)),
          bodySmall: TextStyle(color: AppColors.muted),
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
            ),
          ),
        ),
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
            ),
            side: const BorderSide(color: AppColors.border),
          ),
        ),
      ),
      home: const _ReviewTabs(),
    );
  }
}

class _ReviewTabs extends StatefulWidget {
  const _ReviewTabs();

  @override
  State<_ReviewTabs> createState() => _ReviewTabsState();
}

class _ReviewTabsState extends State<_ReviewTabs> {
  int _index = 0;
  CutsSection _cutsSection = CutsSection.review;

  void _openCuts(CutsSection section) {
    setState(() {
      _index = 1;
      _cutsSection = section;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: [
          HomeScreen(
            onOpenCandidates: () => _openCuts(CutsSection.review),
            onOpenPosts: () => _openCuts(CutsSection.posts),
          ),
          CutsScreen(
            section: _cutsSection,
            onSectionChanged: (section) => setState(() {
              _cutsSection = section;
            }),
            onOpenHome: () => setState(() => _index = 0),
          ),
          MoreScreen(onOpenCandidates: () => _openCuts(CutsSection.review)),
        ],
      ),
      bottomNavigationBar: DFBottomNav(
        selectedIndex: _index,
        onDestinationSelected: (value) => setState(() => _index = value),
      ),
    );
  }
}
