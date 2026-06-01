import 'package:flutter/material.dart';

class ReviewStatusOption {
  const ReviewStatusOption(this.value, this.label, this.icon, this.color);

  final String value;
  final String label;
  final IconData icon;
  final Color color;
}

const statusOptions = [
  ReviewStatusOption(
    'rejected',
    'Rejeitar',
    Icons.thumb_down_alt_rounded,
    Color(0xFFEF4444),
  ),
  ReviewStatusOption(
    'needs_adjustment',
    'Ajustar',
    Icons.tune_rounded,
    Color(0xFFF59E0B),
  ),
  ReviewStatusOption(
    'approved',
    'Aprovar',
    Icons.thumb_up_alt_rounded,
    Color(0xFF10B981),
  ),
];

class StatusButtons extends StatelessWidget {
  const StatusButtons({
    super.key,
    required this.value,
    required this.onChanged,
  });

  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: statusOptions.map((option) {
        final active = value == option.value;
        return Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: InkWell(
              borderRadius: BorderRadius.circular(16),
              onTap: () => onChanged(option.value),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 140),
                height: 64,
                decoration: BoxDecoration(
                  color: active
                      ? option.color.withValues(alpha: 0.16)
                      : const Color(0xFF0F1018),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: active
                        ? option.color.withValues(alpha: 0.55)
                        : Colors.white.withValues(alpha: 0.07),
                    width: active ? 1.5 : 1,
                  ),
                  boxShadow: active
                      ? [
                          BoxShadow(
                            color: option.color.withValues(alpha: 0.18),
                            blurRadius: 18,
                          ),
                        ]
                      : null,
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      option.icon,
                      color: active ? option.color : const Color(0xFF6B7280),
                      size: 21,
                    ),
                    const SizedBox(height: 5),
                    Text(
                      option.label,
                      style: TextStyle(
                        color: active ? option.color : const Color(0xFF6B7280),
                        fontSize: 12,
                        fontWeight: active ? FontWeight.w800 : FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      }).toList(),
    );
  }
}
