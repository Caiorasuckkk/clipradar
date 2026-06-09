import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

class DfMetricCard extends StatelessWidget {
  const DfMetricCard({
    super.key,
    required this.label,
    required this.value,
    this.subtitle,
  });

  final String label;
  final String value;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 86),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact =
              constraints.hasBoundedHeight && constraints.maxHeight < 66;
          final content = Column(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: AppColors.muted,
                  fontSize: compact ? 10 : 12,
                ),
              ),
              SizedBox(height: compact ? 2 : 4),
              ConstrainedBox(
                constraints: BoxConstraints(maxHeight: compact ? 22 : 30),
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    value,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
              ),
              if ((subtitle ?? '').isNotEmpty && !compact) ...[
                const SizedBox(height: 3),
                Text(
                  subtitle!,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: AppColors.muted, fontSize: 11),
                ),
              ],
            ],
          );
          if (constraints.hasBoundedHeight && constraints.maxHeight < 44) {
            return FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: SizedBox(
                width: constraints.hasBoundedWidth ? constraints.maxWidth : 160,
                child: content,
              ),
            );
          }
          return content;
        },
      ),
    );
  }
}
