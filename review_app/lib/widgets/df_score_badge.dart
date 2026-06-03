import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

class DFScoreBadge extends StatelessWidget {
  const DFScoreBadge({super.key, required this.label, required this.score});

  final String label;
  final Object? score;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: AppColors.purple.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppColors.purple.withValues(alpha: 0.35)),
      ),
      child: Text(
        '$label ${score ?? '-'}',
        style: const TextStyle(
          color: AppColors.text,
          fontSize: 12,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}
