import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

class DFGradientCard extends StatelessWidget {
  const DFGradientCard({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.cyan.withValues(alpha: 0.28),
            AppColors.blue.withValues(alpha: 0.30),
            AppColors.purple.withValues(alpha: 0.22),
            AppColors.surface,
          ],
          stops: const [0.0, 0.4, 0.7, 1.0],
        ),
        border: Border.all(color: AppColors.cyan.withValues(alpha: 0.24)),
        boxShadow: [
          BoxShadow(
            color: AppColors.blue.withValues(alpha: 0.22),
            blurRadius: 28,
            offset: const Offset(0, 14),
          ),
        ],
      ),
      child: child,
    );
  }
}
