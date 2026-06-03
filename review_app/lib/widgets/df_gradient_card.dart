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
            AppColors.blue.withValues(alpha: 0.34),
            AppColors.purple.withValues(alpha: 0.24),
            AppColors.surface,
          ],
        ),
        border: Border.all(color: AppColors.cyan.withValues(alpha: 0.22)),
      ),
      child: child,
    );
  }
}
