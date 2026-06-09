import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

class DfStatusChip extends StatelessWidget {
  const DfStatusChip({super.key, required this.label, this.status});

  final String label;
  final String? status;

  @override
  Widget build(BuildContext context) {
    final color = switch (status ?? label) {
      'approved' ||
      'ready_to_post' ||
      'posted' ||
      'success' => AppColors.success,
      'rejected' || 'do_not_post' || 'failed' => AppColors.danger,
      'needs_adjustment' ||
      'needs_edit' ||
      'scheduled' ||
      'success_with_warnings' ||
      'running' => AppColors.warning,
      _ => AppColors.cyan,
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.13),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.36)),
      ),
      child: Text(
        label,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}
