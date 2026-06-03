import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import 'df_empty_state.dart';

class DfErrorState extends StatelessWidget {
  const DfErrorState({super.key, required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return DfEmptyState(
      icon: Icons.wifi_off_rounded,
      title: 'API indisponível',
      message: message,
      onAction: onRetry,
      actionLabel: 'Tentar de novo',
    );
  }
}

class DfInlineError extends StatelessWidget {
  const DfInlineError({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.danger.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.danger.withValues(alpha: 0.25)),
      ),
      child: Text(
        message,
        style: const TextStyle(color: Color(0xFFFCA5A5), fontSize: 12),
      ),
    );
  }
}
