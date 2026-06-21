import 'package:flutter/material.dart';

import 'app_colors.dart';

/// Type scale for DarkFlow.
///
/// Two families with clear roles:
/// - `Sora` (display/titles) gives the brand a bit of character.
/// - `Inter` (everything else) is tuned for UI legibility.
///
/// Weights are limited to those bundled in pubspec (Sora 600/700, Inter
/// 400/500/600/700). Avoid w800/w900 — they fall back to faux-bold.
class AppTextStyles {
  const AppTextStyles._();

  static const _display = 'Sora';
  static const _ui = 'Inter';

  // Display / headings (Sora)
  static const display = TextStyle(
    fontFamily: _display,
    color: AppColors.text,
    fontSize: 28,
    fontWeight: FontWeight.w700,
    height: 1.1,
    letterSpacing: -0.6,
  );
  static const title = TextStyle(
    fontFamily: _display,
    color: AppColors.text,
    fontSize: 24,
    fontWeight: FontWeight.w700,
    height: 1.15,
    letterSpacing: -0.4,
  );
  static const section = TextStyle(
    fontFamily: _display,
    color: AppColors.text,
    fontSize: 18,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.2,
  );

  // UI / body (Inter)
  static const cardTitle = TextStyle(
    fontFamily: _ui,
    color: AppColors.text,
    fontSize: 16,
    fontWeight: FontWeight.w600,
  );
  static const body = TextStyle(
    fontFamily: _ui,
    color: AppColors.text,
    fontSize: 14,
    fontWeight: FontWeight.w400,
    height: 1.45,
  );
  static const bodyStrong = TextStyle(
    fontFamily: _ui,
    color: AppColors.text,
    fontSize: 14,
    fontWeight: FontWeight.w600,
  );
  static const muted = TextStyle(
    fontFamily: _ui,
    color: AppColors.muted,
    fontSize: 12,
    fontWeight: FontWeight.w500,
  );

  /// All-caps section eyebrow (e.g. "ÁREAS", "NÚMEROS").
  static const label = TextStyle(
    fontFamily: _ui,
    color: AppColors.secondaryText,
    fontSize: 11,
    fontWeight: FontWeight.w700,
    letterSpacing: 1.1,
  );
}
