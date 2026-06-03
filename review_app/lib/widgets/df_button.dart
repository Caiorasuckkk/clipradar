import 'package:flutter/material.dart';

class DfButton extends StatelessWidget {
  const DfButton({
    super.key,
    required this.label,
    required this.icon,
    required this.onPressed,
    this.filled = true,
  });

  final String label;
  final IconData icon;
  final VoidCallback? onPressed;
  final bool filled;

  @override
  Widget build(BuildContext context) {
    final child = Text(label, maxLines: 1, overflow: TextOverflow.ellipsis);
    if (filled) {
      return SizedBox(
        height: 48,
        child: FilledButton.icon(
          onPressed: onPressed,
          icon: Icon(icon),
          label: child,
        ),
      );
    }
    return SizedBox(
      height: 48,
      child: OutlinedButton.icon(
        onPressed: onPressed,
        icon: Icon(icon),
        label: child,
      ),
    );
  }
}

class DFPrimaryButton extends StatelessWidget {
  const DFPrimaryButton({
    super.key,
    required this.label,
    required this.icon,
    required this.onPressed,
  });

  final String label;
  final IconData icon;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return DfButton(label: label, icon: icon, onPressed: onPressed);
  }
}

class DFSecondaryButton extends StatelessWidget {
  const DFSecondaryButton({
    super.key,
    required this.label,
    required this.icon,
    required this.onPressed,
  });

  final String label;
  final IconData icon;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return DfButton(
      label: label,
      icon: icon,
      onPressed: onPressed,
      filled: false,
    );
  }
}

class DFGhostButton extends StatelessWidget {
  const DFGhostButton({
    super.key,
    required this.label,
    required this.icon,
    required this.onPressed,
  });

  final String label;
  final IconData icon;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return TextButton.icon(
      onPressed: onPressed,
      icon: Icon(icon),
      label: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis),
    );
  }
}
