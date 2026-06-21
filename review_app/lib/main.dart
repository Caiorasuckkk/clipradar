import 'package:flutter/material.dart';

import 'screens/cuts_screen.dart';
import 'screens/generation_auto_screen.dart';
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
        fontFamily: 'Inter',
        scaffoldBackgroundColor: AppColors.background,
        colorScheme: const ColorScheme.dark(
          primary: AppColors.cyan,
          onPrimary: AppColors.background,
          secondary: AppColors.purple,
          tertiary: AppColors.blue,
          surface: AppColors.surface,
          onSurface: AppColors.text,
          error: AppColors.danger,
          outline: AppColors.border,
        ),
        textTheme: const TextTheme(
          headlineSmall: TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.w700,
            color: AppColors.text,
          ),
          titleLarge: TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.w700,
            color: AppColors.text,
          ),
          titleMedium: TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.w700,
            color: AppColors.text,
          ),
          bodyMedium: TextStyle(color: Color(0xFFC0C4D6)),
          bodySmall: TextStyle(color: AppColors.muted),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.transparent,
          surfaceTintColor: Colors.transparent,
          scrolledUnderElevation: 0,
          centerTitle: false,
          iconTheme: IconThemeData(color: AppColors.text),
          titleTextStyle: TextStyle(
            fontFamily: 'Sora',
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: AppColors.text,
          ),
        ),
        dividerTheme: const DividerThemeData(
          color: AppColors.border,
          thickness: 1,
          space: 1,
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: AppColors.surfaceAlt,
          hintStyle: const TextStyle(color: AppColors.muted),
          labelStyle: const TextStyle(color: AppColors.secondaryText),
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: AppColors.border),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: AppColors.cyan, width: 1.5),
          ),
          disabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: AppColors.border),
          ),
          errorBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: AppColors.danger),
          ),
        ),
        chipTheme: ChipThemeData(
          backgroundColor: AppColors.surfaceAlt,
          selectedColor: AppColors.cyan.withValues(alpha: 0.16),
          side: const BorderSide(color: AppColors.border),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          labelStyle: const TextStyle(
            color: AppColors.secondaryText,
            fontWeight: FontWeight.w600,
          ),
          showCheckmark: false,
        ),
        navigationBarTheme: NavigationBarThemeData(
          backgroundColor: AppColors.secondaryBackground,
          surfaceTintColor: Colors.transparent,
          indicatorColor: AppColors.cyan.withValues(alpha: 0.16),
          elevation: 0,
          height: 68,
          labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
          iconTheme: WidgetStateProperty.resolveWith(
            (states) => IconThemeData(
              size: 24,
              color: states.contains(WidgetState.selected)
                  ? AppColors.cyan
                  : AppColors.muted,
            ),
          ),
          labelTextStyle: WidgetStateProperty.resolveWith(
            (states) => TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: states.contains(WidgetState.selected)
                  ? AppColors.cyan
                  : AppColors.muted,
            ),
          ),
        ),
        snackBarTheme: SnackBarThemeData(
          backgroundColor: AppColors.surface,
          contentTextStyle: const TextStyle(color: AppColors.text),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        dialogTheme: DialogThemeData(
          backgroundColor: AppColors.surface,
          surfaceTintColor: Colors.transparent,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
        ),
        progressIndicatorTheme: const ProgressIndicatorThemeData(
          color: AppColors.cyan,
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            backgroundColor: AppColors.cyan,
            foregroundColor: AppColors.background,
            minimumSize: const Size(0, 50),
            textStyle: const TextStyle(
              fontFamily: 'Inter',
              fontWeight: FontWeight.w700,
              fontSize: 15,
            ),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
            ),
          ),
        ),
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            foregroundColor: AppColors.text,
            minimumSize: const Size(0, 50),
            textStyle: const TextStyle(
              fontFamily: 'Inter',
              fontWeight: FontWeight.w700,
              fontSize: 14,
            ),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
            ),
            side: const BorderSide(color: AppColors.border),
          ),
        ),
        textButtonTheme: TextButtonThemeData(
          style: TextButton.styleFrom(
            foregroundColor: AppColors.cyan,
            textStyle: const TextStyle(fontWeight: FontWeight.w700),
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

  void _openGeneration() {
    setState(() => _index = 2);
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
            onOpenAnalytics: () => _openCuts(CutsSection.analytics),
            onOpenGeneration: _openGeneration,
          ),
          CutsScreen(
            section: _cutsSection,
            onSectionChanged: (section) => setState(() {
              _cutsSection = section;
            }),
            onOpenHome: () => setState(() => _index = 0),
          ),
          const GenerationAutoScreen(),
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
