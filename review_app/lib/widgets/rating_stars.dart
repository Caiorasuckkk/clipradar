import 'package:flutter/material.dart';

class RatingStars extends StatelessWidget {
  const RatingStars({super.key, required this.value, required this.onChanged});

  final int value;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _Label('Nota do corte'),
          const SizedBox(height: 10),
          Row(
            children: List.generate(5, (index) {
              final starValue = index + 1;
              final active = starValue <= value;
              return Expanded(
                child: InkWell(
                  borderRadius: BorderRadius.circular(14),
                  onTap: () => onChanged(starValue),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Icon(
                      active ? Icons.star_rounded : Icons.star_border_rounded,
                      color: active
                          ? const Color(0xFFF59E0B)
                          : const Color(0xFF4B5563),
                      size: 36,
                    ),
                  ),
                ),
              );
            }),
          ),
        ],
      ),
    );
  }
}

class _Panel extends StatelessWidget {
  const _Panel({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1018),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withValues(alpha: 0.07)),
      ),
      child: child,
    );
  }
}

class _Label extends StatelessWidget {
  const _Label(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: const TextStyle(
        color: Color(0xFF6B7280),
        fontSize: 10,
        letterSpacing: 0.8,
        fontWeight: FontWeight.w700,
      ),
    );
  }
}
