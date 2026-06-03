import 'package:flutter/material.dart';

import 'app_colors.dart';

class AppTextStyles {
  const AppTextStyles._();

  static const title = TextStyle(
    color: AppColors.text,
    fontSize: 24,
    fontWeight: FontWeight.w900,
  );
  static const section = TextStyle(
    color: AppColors.text,
    fontSize: 18,
    fontWeight: FontWeight.w900,
  );
  static const cardTitle = TextStyle(
    color: AppColors.text,
    fontSize: 16,
    fontWeight: FontWeight.w900,
  );
  static const body = TextStyle(color: AppColors.text, fontSize: 14);
  static const muted = TextStyle(color: AppColors.muted, fontSize: 12);
}
