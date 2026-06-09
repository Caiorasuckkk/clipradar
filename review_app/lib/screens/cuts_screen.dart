import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import 'candidate_clips_screen.dart';
import 'posts_screen.dart';

enum CutsSection { review, posts }

class CutsScreen extends StatelessWidget {
  const CutsScreen({
    super.key,
    required this.section,
    required this.onSectionChanged,
    this.onOpenHome,
  });

  final CutsSection section;
  final ValueChanged<CutsSection> onSectionChanged;
  final VoidCallback? onOpenHome;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 16, 18, 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Cortes', style: AppTextStyles.title),
                  const SizedBox(height: 4),
                  const Text(
                    'Revise cortes e acompanhe os prontos para postar.',
                    style: TextStyle(color: AppColors.secondaryText),
                  ),
                  const SizedBox(height: 14),
                  SegmentedButton<CutsSection>(
                    segments: const [
                      ButtonSegment(
                        value: CutsSection.review,
                        icon: Icon(Icons.swipe_rounded),
                        label: Text('Avaliar'),
                      ),
                      ButtonSegment(
                        value: CutsSection.posts,
                        icon: Icon(Icons.publish_rounded),
                        label: Text('Posts'),
                      ),
                    ],
                    selected: {section},
                    onSelectionChanged: (value) =>
                        onSectionChanged(value.first),
                  ),
                ],
              ),
            ),
            Expanded(
              child: section == CutsSection.review
                  ? CandidateClipsScreen(
                      embedded: true,
                      onOpenHome: onOpenHome,
                      onOpenPosts: () => onSectionChanged(CutsSection.posts),
                    )
                  : const PostsScreen(embedded: true),
            ),
          ],
        ),
      ),
    );
  }
}
