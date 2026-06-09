import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../models/cuts_analytics.dart';
import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import 'candidate_clips_screen.dart';
import 'cuts_analytics_screen.dart';
import 'posts_screen.dart';

enum CutsSection { review, posts, analytics }

class CutsScreen extends StatefulWidget {
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
  State<CutsScreen> createState() => _CutsScreenState();
}

class _CutsScreenState extends State<CutsScreen> {
  final ApiClient _api = ApiClient();
  CutsAnalytics? _analytics;

  @override
  void initState() {
    super.initState();
    _loadSummary();
  }

  Future<void> _loadSummary() async {
    try {
      final analytics = await _api.fetchCutsAnalytics();
      if (!mounted) return;
      setState(() => _analytics = analytics);
    } catch (_) {
      // The hub stays usable even when analytics is temporarily unavailable.
    }
  }

  @override
  Widget build(BuildContext context) {
    final subtitle = _analytics == null
        ? 'Revise cortes e acompanhe seus posts.'
        : _summaryText(_analytics!.overview);
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
                  Text(
                    subtitle,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
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
                      ButtonSegment(
                        value: CutsSection.analytics,
                        icon: Icon(Icons.query_stats_rounded),
                        label: Text('Analytics'),
                      ),
                    ],
                    selected: {widget.section},
                    onSelectionChanged: (value) =>
                        widget.onSectionChanged(value.first),
                  ),
                ],
              ),
            ),
            Expanded(child: _sectionBody()),
          ],
        ),
      ),
    );
  }

  Widget _sectionBody() {
    return switch (widget.section) {
      CutsSection.review => CandidateClipsScreen(
        embedded: true,
        onOpenHome: widget.onOpenHome,
        onOpenPosts: () => widget.onSectionChanged(CutsSection.posts),
      ),
      CutsSection.posts => const PostsScreen(embedded: true),
      CutsSection.analytics => const CutsAnalyticsScreen(),
    };
  }

  String _summaryText(CutsAnalyticsOverview overview) {
    if (overview.totalCandidates == 0 && overview.generatedPostsCount == 0) {
      return 'Revise cortes e acompanhe seus posts.';
    }
    final approval = (overview.approvalRate * 100).round();
    return '${overview.pending} pendentes • ${overview.generatedPostsCount} posts • $approval% aprovados';
  }
}
