import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

class DfLoadingState extends StatelessWidget {
  const DfLoadingState({super.key, this.message = 'Carregando...'});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(color: AppColors.cyan),
          const SizedBox(height: 12),
          Text(message, style: const TextStyle(color: AppColors.muted)),
        ],
      ),
    );
  }
}
