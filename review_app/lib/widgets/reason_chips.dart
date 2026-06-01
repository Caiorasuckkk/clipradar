import 'package:flutter/material.dart';

class ReasonOption {
  const ReasonOption(this.value, this.label, this.group, this.color);

  final String value;
  final String label;
  final String group;
  final Color color;
}

const reasonOptions = [
  ReasonOption('bom', 'bom', 'Positivos', Color(0xFF10B981)),
  ReasonOption('otimo', 'otimo', 'Positivos', Color(0xFF10B981)),
  ReasonOption('perfeito', 'perfeito', 'Positivos', Color(0xFF10B981)),
  ReasonOption('bom_longo', 'bom mas longo', 'Ajustes', Color(0xFFF59E0B)),
  ReasonOption(
    'final_encurtar',
    'final encurtar',
    'Ajustes',
    Color(0xFFF59E0B),
  ),
  ReasonOption('precisa_trim', 'precisa trim', 'Ajustes', Color(0xFFF59E0B)),
  ReasonOption('topic_merge', 'topic merge', 'Ajustes', Color(0xFFF59E0B)),
  ReasonOption('ruim', 'ruim', 'Negativos', Color(0xFFEF4444)),
  ReasonOption('sem_contexto', 'sem contexto', 'Negativos', Color(0xFFEF4444)),
  ReasonOption('nao_prendeu', 'nao prendeu', 'Negativos', Color(0xFFEF4444)),
  ReasonOption('propaganda', 'propaganda', 'Negativos', Color(0xFFEF4444)),
];

class ReasonChips extends StatelessWidget {
  const ReasonChips({
    super.key,
    required this.selected,
    required this.onChanged,
  });

  final String selected;
  final ValueChanged<String> onChanged;

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
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'MOTIVOS RAPIDOS',
            style: TextStyle(
              color: Color(0xFF6B7280),
              fontSize: 10,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.8,
            ),
          ),
          const SizedBox(height: 12),
          for (final group in ['Positivos', 'Ajustes', 'Negativos']) ...[
            Text(
              group,
              style: const TextStyle(color: Color(0xFF6B7280), fontSize: 11),
            ),
            const SizedBox(height: 7),
            Wrap(
              spacing: 7,
              runSpacing: 7,
              children: reasonOptions.where((item) => item.group == group).map((
                item,
              ) {
                final active = selected == item.value;
                return ChoiceChip(
                  selected: active,
                  label: Text(item.label),
                  onSelected: (_) => onChanged(item.value),
                  labelStyle: TextStyle(
                    color: active ? item.color : const Color(0xFF9CA3AF),
                    fontSize: 12,
                    fontWeight: active ? FontWeight.w800 : FontWeight.w500,
                  ),
                  selectedColor: item.color.withValues(alpha: 0.16),
                  backgroundColor: const Color(0xFF1A1C28),
                  side: BorderSide(
                    color: active
                        ? item.color.withValues(alpha: 0.48)
                        : Colors.white.withValues(alpha: 0.07),
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(18),
                  ),
                  showCheckmark: false,
                );
              }).toList(),
            ),
            if (group != 'Negativos') const SizedBox(height: 12),
          ],
        ],
      ),
    );
  }
}
