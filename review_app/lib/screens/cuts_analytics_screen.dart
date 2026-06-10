import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../models/cuts_analytics.dart';
import '../theme/app_colors.dart';
import '../widgets/df_card.dart';
import '../widgets/df_error_state.dart';
import '../widgets/df_loading_state.dart';
import '../widgets/df_metric_card.dart';

class CutsAnalyticsScreen extends StatefulWidget {
  const CutsAnalyticsScreen({super.key});

  @override
  State<CutsAnalyticsScreen> createState() => _CutsAnalyticsScreenState();
}

class _CutsAnalyticsScreenState extends State<CutsAnalyticsScreen> {
  final ApiClient _api = ApiClient();
  CutsAnalytics? _analytics;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final analytics = await _api.fetchCutsAnalytics();
      if (!mounted) return;
      setState(() {
        _analytics = analytics;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading && _analytics == null) {
      return const DfLoadingState(message: 'Carregando analytics...');
    }
    if (_error != null && _analytics == null) {
      return Padding(
        padding: const EdgeInsets.all(18),
        child: DfErrorState(message: _error!, onRetry: _load),
      );
    }
    final analytics = _analytics!;
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(14, 4, 14, 18),
        children: [
          if (_error != null) _InlineWarning(message: _error!),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: _loading ? null : _load,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Atualizar analytics'),
            ),
          ),
          const SizedBox(height: 6),
          _OverviewGrid(overview: analytics.overview),
          const SizedBox(height: 12),
          _CacheCard(cache: analytics.cache),
          const SizedBox(height: 12),
          _SourceQualityCard(source: analytics.sourceIntelligence),
          const SizedBox(height: 12),
          _CandidateQualityCard(quality: analytics.candidateQuality),
          const SizedBox(height: 12),
          _ReasonsCard(overview: analytics.overview),
          const SizedBox(height: 12),
          _TopVideosCard(videos: analytics.byVideo.take(8).toList()),
          const SizedBox(height: 12),
          _SourcesCard(sources: analytics.bySource),
          const SizedBox(height: 12),
          _JobsCard(jobs: analytics.jobs),
        ],
      ),
    );
  }
}

class _OverviewGrid extends StatelessWidget {
  const _OverviewGrid({required this.overview});

  final CutsAnalyticsOverview overview;

  @override
  Widget build(BuildContext context) {
    final metrics = [
      ('Pendentes', '${overview.pending}'),
      ('Prontos', '${overview.previewReady}'),
      ('Aprovados', '${overview.approved}'),
      ('Rejeitados', '${overview.rejected}'),
      ('Taxa aprov.', _percent(overview.approvalRate)),
      ('Posts', '${overview.generatedPostsCount}'),
    ];
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: metrics.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        crossAxisSpacing: 10,
        mainAxisSpacing: 10,
        mainAxisExtent: 96,
      ),
      itemBuilder: (context, index) {
        final metric = metrics[index];
        return DfMetricCard(label: metric.$1, value: metric.$2);
      },
    );
  }
}

class _CacheCard extends StatelessWidget {
  const _CacheCard({required this.cache});

  final CutsAnalyticsCache cache;

  @override
  Widget build(BuildContext context) {
    return DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _CardTitle(
            icon: Icons.cached_rounded,
            title: 'Cache e economia',
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _ChipMetric(label: 'vídeos', value: '${cache.totalVideosCached}'),
              _ChipMetric(
                label: 'transcrições',
                value: '${cache.transcriptCachedCount}',
              ),
              _ChipMetric(
                label: 'previews',
                value: '${cache.previewsCachedCount}',
              ),
              _ChipMetric(label: 'finais', value: '${cache.finalsCachedCount}'),
              _ChipMetric(
                label: 'hits última',
                value: '${cache.cacheHitsLatestRun}',
              ),
              _ChipMetric(
                label: 'parciais',
                value: '${cache.cachePartialsLatestRun}',
              ),
              _ChipMetric(
                label: 'bypass',
                value: '${cache.cacheBypassedLatestRun}',
              ),
              _ChipMetric(
                label: 'zero',
                value: '${cache.videosProcessedFromScratchLatestRun}',
              ),
              _ChipMetric(label: 'stale', value: '${cache.staleCount}'),
              _ChipMetric(
                label: 'dup cand.',
                value: '${cache.duplicateCandidatesDetectedLatestRun}',
              ),
              _ChipMetric(
                label: 'dup posts',
                value: '${cache.duplicatePostsDetected}',
              ),
              _ChipMetric(
                label: 'aprov. sem final',
                value: '${cache.approvedMissingFinals}',
              ),
              _ChipMetric(
                label: 'finais órfãos',
                value: '${cache.orphanFinals}',
              ),
              _ChipMetric(label: 'posts órfãos', value: '${cache.orphanPosts}'),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            'Reaproveitados na última busca: ${cache.videosReusedLatestRun} • economia estimada: ${_seconds(cache.estimatedSecondsSavedLatestRun)}',
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: AppColors.secondaryText),
          ),
        ],
      ),
    );
  }
}

class _SourceQualityCard extends StatelessWidget {
  const _SourceQualityCard({required this.source});

  final CutsAnalyticsSourceIntelligence source;

  @override
  Widget build(BuildContext context) {
    final reasons = source.worstRejectionReasons;
    final channels = source.bestChannelsByApprovalRate;
    return DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _CardTitle(
            icon: Icons.travel_explore_rounded,
            title: 'Qualidade das fontes',
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _ChipMetric(
                label: 'encontrados',
                value: '${source.latestDiscoveredCount}',
              ),
              _ChipMetric(
                label: 'aceitos',
                value: '${source.latestAcceptedCount}',
              ),
              _ChipMetric(
                label: 'rejeitados',
                value: '${source.latestRejectedCount}',
              ),
              _ChipMetric(
                label: 'duras',
                value: '${source.latestHardRejectedCount}',
              ),
              _ChipMetric(
                label: 'flexíveis',
                value: '${source.latestSoftRejectedCount}',
              ),
              _ChipMetric(
                label: 'fallback',
                value: source.latestFallbackUsed
                    ? '${source.latestFallbackSelectedCount}'
                    : 'não',
              ),
              _ChipMetric(
                label: 'score médio',
                value: source.latestAverageSourceScore.toStringAsFixed(1),
              ),
            ],
          ),
          if (reasons.isNotEmpty) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: reasons.take(5).map((item) {
                return _ChipMetric(
                  label: '${item['reason'] ?? '-'}',
                  value: '${item['count'] ?? 0}',
                );
              }).toList(),
            ),
          ],
          if (channels.isNotEmpty) ...[
            const SizedBox(height: 10),
            ...channels.take(3).map((item) {
              final rate = item['approval_rate'] is num
                  ? (item['approval_rate'] as num).toDouble()
                  : 0.0;
              return _CompactRow(
                title: '${item['name'] ?? 'fonte'}',
                subtitle:
                    '${item['approved'] ?? 0} aprov. • ${item['total'] ?? 0} cortes',
                trailing: _percent(rate),
              );
            }),
          ],
        ],
      ),
    );
  }
}

class _CandidateQualityCard extends StatelessWidget {
  const _CandidateQualityCard({required this.quality});

  final CutsAnalyticsCandidateQuality quality;

  @override
  Widget build(BuildContext context) {
    final positives = quality.latestTopPositiveSignals.isNotEmpty
        ? quality.latestTopPositiveSignals
        : quality.topPositiveSignals;
    final negatives = quality.latestBottomNegativeSignals.isNotEmpty
        ? quality.latestBottomNegativeSignals
        : quality.topNegativeSignals;
    return DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _CardTitle(
            icon: Icons.workspace_premium_rounded,
            title: 'Qualidade dos cortes',
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _ChipMetric(
                label: 'score médio',
                value: quality.averageQualityScore.toStringAsFixed(1),
              ),
              _ChipMetric(
                label: 'mediana',
                value: _score(quality.latestScoreP50),
              ),
              _ChipMetric(label: 'p75', value: _score(quality.latestScoreP75)),
              _ChipMetric(
                label: 'excelentes',
                value: '${quality.excellentCount}',
              ),
              _ChipMetric(label: 'bons', value: '${quality.goodCount}'),
              _ChipMetric(label: 'fracos', value: '${quality.weakCount}'),
              _ChipMetric(
                label: 'rejeitados',
                value: '${quality.rejectedCount}',
              ),
              _ChipMetric(
                label: 'filtrados',
                value: '${quality.latestQualityRejected}',
              ),
              _ChipMetric(
                label: 'rejeição dura',
                value: '${quality.latestHardRejected}',
              ),
              _ChipMetric(
                label: 'rejeição score',
                value: '${quality.latestScoreRejected}',
              ),
              _ChipMetric(
                label: 'dup texto',
                value: '${quality.latestDuplicatesRemovedByText}',
              ),
              _ChipMetric(
                label: 'dup tempo',
                value: '${quality.latestDuplicatesRemovedByTime}',
              ),
              _ChipMetric(
                label: 'fallback',
                value: quality.latestQualityFallbackUsed ? 'sim' : 'não',
              ),
            ],
          ),
          if (positives.isNotEmpty || negatives.isNotEmpty) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ...positives.take(4).map((item) {
                  return _ChipMetric(
                    label: '${item['signal'] ?? '-'}',
                    value: '${item['count'] ?? 0}',
                  );
                }),
                ...negatives.take(4).map((item) {
                  return _ChipMetric(
                    label: '${item['signal'] ?? '-'}',
                    value: '${item['count'] ?? 0}',
                  );
                }),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _ReasonsCard extends StatelessWidget {
  const _ReasonsCard({required this.overview});

  final CutsAnalyticsOverview overview;

  @override
  Widget build(BuildContext context) {
    final reasons = overview.countByReason.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _CardTitle(icon: Icons.sell_rounded, title: 'Motivos'),
          const SizedBox(height: 10),
          if (reasons.isEmpty)
            const Text(
              'Ainda sem reviews suficientes.',
              style: TextStyle(color: AppColors.muted),
            )
          else
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: reasons.take(8).map((entry) {
                return _ChipMetric(label: entry.key, value: '${entry.value}');
              }).toList(),
            ),
        ],
      ),
    );
  }
}

class _TopVideosCard extends StatelessWidget {
  const _TopVideosCard({required this.videos});

  final List<CutsAnalyticsVideo> videos;

  @override
  Widget build(BuildContext context) {
    return DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _CardTitle(
            icon: Icons.video_collection_rounded,
            title: 'Melhores vídeos',
          ),
          const SizedBox(height: 10),
          if (videos.isEmpty)
            const Text(
              'Nenhum vídeo com dados ainda.',
              style: TextStyle(color: AppColors.muted),
            )
          else
            ...videos.map(_VideoRow.new),
        ],
      ),
    );
  }
}

class _SourcesCard extends StatelessWidget {
  const _SourcesCard({required this.sources});

  final List<CutsAnalyticsSource> sources;

  @override
  Widget build(BuildContext context) {
    return DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _CardTitle(icon: Icons.source_rounded, title: 'Fontes'),
          const SizedBox(height: 10),
          if (sources.isEmpty)
            const Text(
              'Nenhuma fonte mapeada.',
              style: TextStyle(color: AppColors.muted),
            )
          else
            ...sources.take(8).map(_SourceRow.new),
        ],
      ),
    );
  }
}

class _JobsCard extends StatelessWidget {
  const _JobsCard({required this.jobs});

  final CutsAnalyticsJobs jobs;

  @override
  Widget build(BuildContext context) {
    final latest = jobs.latestSearch;
    return DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _CardTitle(icon: Icons.query_stats_rounded, title: 'Buscas'),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _ChipMetric(label: 'runs', value: '${jobs.searchRunsCount}'),
              _ChipMetric(
                label: 'rápidas',
                value: '${jobs.fastSearchRunsCount}',
              ),
              _ChipMetric(
                label: 'profundas',
                value: '${jobs.deepSearchRunsCount}',
              ),
              _ChipMetric(
                label: 'avisos',
                value: '${jobs.successWithWarningsCount}',
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (latest.runId.isEmpty)
            const Text(
              'Nenhuma busca registrada ainda.',
              style: TextStyle(color: AppColors.muted),
            )
          else
            _LatestRun(latest: latest),
        ],
      ),
    );
  }
}

class _VideoRow extends StatelessWidget {
  const _VideoRow(this.video);

  final CutsAnalyticsVideo video;

  @override
  Widget build(BuildContext context) {
    final title = video.videoTitle.isNotEmpty
        ? video.videoTitle
        : video.videoId;
    return _CompactRow(
      title: title,
      subtitle:
          '${video.approvedCount} aprov. • ${video.reviewed} rev. • ${_percent(video.approvalRate)} • score ${_score(video.averageScore)}',
      trailing: video.generatedPostsCount > 0
          ? '${video.generatedPostsCount} posts'
          : '${video.previewReady} prontos',
    );
  }
}

class _SourceRow extends StatelessWidget {
  const _SourceRow(this.source);

  final CutsAnalyticsSource source;

  @override
  Widget build(BuildContext context) {
    return _CompactRow(
      title: source.source,
      subtitle:
          '${source.approvedCount} aprov. • ${source.totalCandidates} cortes',
      trailing: _percent(source.approvalRate),
    );
  }
}

class _LatestRun extends StatelessWidget {
  const _LatestRun({required this.latest});

  final CutsAnalyticsLatestSearch latest;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.secondaryBackground,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Última busca: ${latest.status}',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 4),
          Text(
            '${latest.previewReady} prontos • ${latest.pendingReviewableCount} pendentes • ${_seconds(latest.elapsedSeconds)} • ${latest.nextAction}',
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: AppColors.secondaryText),
          ),
          if (latest.warningMessage.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              latest.warningMessage,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: AppColors.warning),
            ),
          ],
        ],
      ),
    );
  }
}

class _CompactRow extends StatelessWidget {
  const _CompactRow({
    required this.title,
    required this.subtitle,
    required this.trailing,
  });

  final String title;
  final String subtitle;
  final String trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppColors.secondaryText,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Text(
            trailing,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppColors.cyan,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _CardTitle extends StatelessWidget {
  const _CardTitle({required this.icon, required this.title});

  final IconData icon;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, color: AppColors.cyan, size: 20),
        const SizedBox(width: 8),
        Text(
          title,
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900),
        ),
      ],
    );
  }
}

class _ChipMetric extends StatelessWidget {
  const _ChipMetric({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: AppColors.cyan.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppColors.cyan.withValues(alpha: 0.22)),
      ),
      child: Text(
        '$label $value',
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(color: AppColors.text, fontSize: 12),
      ),
    );
  }
}

class _InlineWarning extends StatelessWidget {
  const _InlineWarning({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.warning.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.warning.withValues(alpha: 0.24)),
        ),
        child: Text(
          message,
          maxLines: 3,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(color: AppColors.warning),
        ),
      ),
    );
  }
}

String _percent(double value) => '${(value * 100).round()}%';

String _score(num? value) => value == null ? '-' : value.toStringAsFixed(1);

String _seconds(num? value) {
  if (value == null) return '-';
  return '${value.round()}s';
}
