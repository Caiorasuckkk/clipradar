import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

class DFBottomNav extends StatelessWidget {
  const DFBottomNav({
    super.key,
    required this.selectedIndex,
    required this.onDestinationSelected,
  });

  final int selectedIndex;
  final ValueChanged<int> onDestinationSelected;

  @override
  Widget build(BuildContext context) {
    return NavigationBar(
      selectedIndex: selectedIndex,
      onDestinationSelected: onDestinationSelected,
      backgroundColor: AppColors.secondaryBackground,
      indicatorColor: AppColors.cyan.withValues(alpha: 0.16),
      destinations: const [
        NavigationDestination(icon: Icon(Icons.home_rounded), label: 'Início'),
        NavigationDestination(
          icon: Icon(Icons.swipe_rounded),
          label: 'Avaliar',
        ),
        NavigationDestination(
          icon: Icon(Icons.publish_rounded),
          label: 'Posts',
        ),
        NavigationDestination(
          icon: Icon(Icons.more_horiz_rounded),
          label: 'Mais',
        ),
      ],
    );
  }
}
