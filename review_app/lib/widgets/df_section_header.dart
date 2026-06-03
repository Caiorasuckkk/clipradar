import 'package:flutter/material.dart';

import '../theme/app_text_styles.dart';

class DfSectionHeader extends StatelessWidget {
  const DfSectionHeader({super.key, required this.title, this.subtitle});

  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: AppTextStyles.section),
          if (subtitle != null) ...[
            const SizedBox(height: 3),
            Text(subtitle!, style: AppTextStyles.muted),
          ],
        ],
      ),
    );
  }
}
