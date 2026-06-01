import 'package:flutter/material.dart';

import '../models/review_summary.dart';

class SummaryCard extends StatelessWidget {
  const SummaryCard({
    super.key,
    required this.summary,
    required this.onRefresh,
  });

  final ReviewSummary? summary;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    const cyan = Color(0xFF00C8F0);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1018),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withValues(alpha: 0.07)),
      ),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: cyan.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.bolt_rounded, color: cyan, size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Wrap(
              spacing: 12,
              runSpacing: 6,
              children: [
                _Metric(
                  label: 'Total',
                  value: '${summary?.totalExported ?? 0}',
                  color: Colors.white70,
                ),
                _Metric(
                  label: 'Rev.',
                  value: '${summary?.totalReviewed ?? 0}',
                  color: cyan,
                ),
                _Metric(
                  label: 'Pend.',
                  value: '${summary?.pending ?? 0}',
                  color: cyan,
                ),
                _Metric(
                  label: 'Ok',
                  value: '${summary?.approved ?? 0}',
                  color: const Color(0xFF10B981),
                ),
                _Metric(
                  label: 'No',
                  value: '${summary?.rejected ?? 0}',
                  color: const Color(0xFFEF4444),
                ),
                _Metric(
                  label: 'Trim',
                  value: '${summary?.needsAdjustment ?? 0}',
                  color: const Color(0xFFF59E0B),
                ),
                _Metric(
                  label: 'Avg',
                  value: summary?.averageRating?.toStringAsFixed(1) ?? '-',
                  color: Colors.white70,
                ),
              ],
            ),
          ),
          IconButton(
            onPressed: onRefresh,
            icon: const Icon(Icons.refresh_rounded, color: Color(0xFF8C93A6)),
          ),
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          value,
          style: TextStyle(
            color: color,
            fontWeight: FontWeight.w800,
            fontSize: 17,
          ),
        ),
        Text(
          label,
          style: const TextStyle(
            color: Color(0xFF6B7280),
            fontSize: 10,
            letterSpacing: 0,
          ),
        ),
      ],
    );
  }
}
