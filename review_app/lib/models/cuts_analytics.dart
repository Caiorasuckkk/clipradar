class CutsAnalytics {
  const CutsAnalytics({
    required this.overview,
    required this.byVideo,
    required this.bySource,
    required this.jobs,
    required this.cache,
    required this.sourceIntelligence,
  });

  final CutsAnalyticsOverview overview;
  final List<CutsAnalyticsVideo> byVideo;
  final List<CutsAnalyticsSource> bySource;
  final CutsAnalyticsJobs jobs;
  final CutsAnalyticsCache cache;
  final CutsAnalyticsSourceIntelligence sourceIntelligence;

  factory CutsAnalytics.fromJson(Map<String, dynamic> json) {
    return CutsAnalytics(
      overview: CutsAnalyticsOverview.fromJson(_map(json['overview'])),
      byVideo: _list(
        json['by_video'],
      ).map(CutsAnalyticsVideo.fromJson).toList(),
      bySource: _list(
        json['by_source'],
      ).map(CutsAnalyticsSource.fromJson).toList(),
      jobs: CutsAnalyticsJobs.fromJson(_map(json['jobs'])),
      cache: CutsAnalyticsCache.fromJson(_map(json['cache'])),
      sourceIntelligence: CutsAnalyticsSourceIntelligence.fromJson(
        _map(json['source_intelligence']),
      ),
    );
  }
}

class CutsAnalyticsOverview {
  const CutsAnalyticsOverview({
    required this.totalCandidates,
    required this.previewReady,
    required this.missingPreview,
    required this.reviewed,
    required this.pending,
    required this.approved,
    required this.rejected,
    required this.needsAdjustment,
    required this.approvalRate,
    required this.rejectionRate,
    required this.adjustmentRate,
    required this.averageRating,
    required this.countByReason,
    required this.generatedPostsCount,
    required this.notPostedCount,
    required this.postedCount,
    required this.scheduledCount,
    required this.doNotPostCount,
  });

  final int totalCandidates;
  final int previewReady;
  final int missingPreview;
  final int reviewed;
  final int pending;
  final int approved;
  final int rejected;
  final int needsAdjustment;
  final double approvalRate;
  final double rejectionRate;
  final double adjustmentRate;
  final num? averageRating;
  final Map<String, int> countByReason;
  final int generatedPostsCount;
  final int notPostedCount;
  final int postedCount;
  final int scheduledCount;
  final int doNotPostCount;

  factory CutsAnalyticsOverview.fromJson(Map<String, dynamic> json) {
    return CutsAnalyticsOverview(
      totalCandidates: _int(json['total_candidates']),
      previewReady: _int(json['preview_ready']),
      missingPreview: _int(json['missing_preview']),
      reviewed: _int(json['reviewed']),
      pending: _int(json['pending']),
      approved: _int(json['approved']),
      rejected: _int(json['rejected']),
      needsAdjustment: _int(json['needs_adjustment']),
      approvalRate: _double(json['approval_rate']),
      rejectionRate: _double(json['rejection_rate']),
      adjustmentRate: _double(json['adjustment_rate']),
      averageRating: _num(json['average_rating']),
      countByReason: _intMap(json['count_by_reason']),
      generatedPostsCount: _int(json['generated_posts_count']),
      notPostedCount: _int(json['not_posted_count']),
      postedCount: _int(json['posted_count']),
      scheduledCount: _int(json['scheduled_count']),
      doNotPostCount: _int(json['do_not_post_count']),
    );
  }
}

class CutsAnalyticsVideo {
  const CutsAnalyticsVideo({
    required this.videoId,
    required this.videoTitle,
    required this.totalCandidates,
    required this.previewReady,
    required this.missingPreview,
    required this.reviewed,
    required this.pending,
    required this.approvedCount,
    required this.rejectedCount,
    required this.needsAdjustmentCount,
    required this.approvalRate,
    required this.averageRating,
    required this.averageScore,
    required this.generatedPostsCount,
  });

  final String videoId;
  final String videoTitle;
  final int totalCandidates;
  final int previewReady;
  final int missingPreview;
  final int reviewed;
  final int pending;
  final int approvedCount;
  final int rejectedCount;
  final int needsAdjustmentCount;
  final double approvalRate;
  final num? averageRating;
  final num? averageScore;
  final int generatedPostsCount;

  factory CutsAnalyticsVideo.fromJson(Map<String, dynamic> json) {
    return CutsAnalyticsVideo(
      videoId: _string(json['video_id']),
      videoTitle: _string(json['video_title']),
      totalCandidates: _int(json['total_candidates']),
      previewReady: _int(json['preview_ready']),
      missingPreview: _int(json['missing_preview']),
      reviewed: _int(json['reviewed']),
      pending: _int(json['pending']),
      approvedCount: _int(json['approved_count']),
      rejectedCount: _int(json['rejected_count']),
      needsAdjustmentCount: _int(json['needs_adjustment_count']),
      approvalRate: _double(json['approval_rate']),
      averageRating: _num(json['average_rating']),
      averageScore: _num(json['average_score']),
      generatedPostsCount: _int(json['generated_posts_count']),
    );
  }
}

class CutsAnalyticsSource {
  const CutsAnalyticsSource({
    required this.source,
    required this.totalCandidates,
    required this.reviewed,
    required this.approvedCount,
    required this.rejectedCount,
    required this.needsAdjustmentCount,
    required this.approvalRate,
    required this.averageRating,
    required this.averageScore,
  });

  final String source;
  final int totalCandidates;
  final int reviewed;
  final int approvedCount;
  final int rejectedCount;
  final int needsAdjustmentCount;
  final double approvalRate;
  final num? averageRating;
  final num? averageScore;

  factory CutsAnalyticsSource.fromJson(Map<String, dynamic> json) {
    return CutsAnalyticsSource(
      source: _string(json['source_collection']).isNotEmpty
          ? _string(json['source_collection'])
          : _string(json['source']),
      totalCandidates: _int(json['total_candidates']),
      reviewed: _int(json['reviewed']),
      approvedCount: _int(json['approved_count']),
      rejectedCount: _int(json['rejected_count']),
      needsAdjustmentCount: _int(json['needs_adjustment_count']),
      approvalRate: _double(json['approval_rate']),
      averageRating: _num(json['average_rating']),
      averageScore: _num(json['average_score']),
    );
  }
}

class CutsAnalyticsJobs {
  const CutsAnalyticsJobs({
    required this.searchRunsCount,
    required this.fastSearchRunsCount,
    required this.deepSearchRunsCount,
    required this.successCount,
    required this.successWithWarningsCount,
    required this.failedCount,
    required this.cancelledCount,
    required this.averageSearchElapsedSeconds,
    required this.averageTimeToFirstReviewableSeconds,
    required this.latestSearch,
  });

  final int searchRunsCount;
  final int fastSearchRunsCount;
  final int deepSearchRunsCount;
  final int successCount;
  final int successWithWarningsCount;
  final int failedCount;
  final int cancelledCount;
  final num? averageSearchElapsedSeconds;
  final num? averageTimeToFirstReviewableSeconds;
  final CutsAnalyticsLatestSearch latestSearch;

  factory CutsAnalyticsJobs.fromJson(Map<String, dynamic> json) {
    return CutsAnalyticsJobs(
      searchRunsCount: _int(json['search_runs_count']),
      fastSearchRunsCount: _int(json['fast_search_runs_count']),
      deepSearchRunsCount: _int(json['deep_search_runs_count']),
      successCount: _int(json['success_count']),
      successWithWarningsCount: _int(json['success_with_warnings_count']),
      failedCount: _int(json['failed_count']),
      cancelledCount: _int(json['cancelled_count']),
      averageSearchElapsedSeconds: _num(json['average_search_elapsed_seconds']),
      averageTimeToFirstReviewableSeconds: _num(
        json['average_time_to_first_reviewable_seconds'],
      ),
      latestSearch: CutsAnalyticsLatestSearch.fromJson(
        _map(json['latest_search']),
      ),
    );
  }
}

class CutsAnalyticsLatestSearch {
  const CutsAnalyticsLatestSearch({
    required this.runId,
    required this.status,
    required this.startedAt,
    required this.finishedAt,
    required this.elapsedSeconds,
    required this.candidateCount,
    required this.previewReady,
    required this.missingPreview,
    required this.pendingReviewableCount,
    required this.nextAction,
    required this.latestError,
    required this.warningMessage,
  });

  final String runId;
  final String status;
  final String startedAt;
  final String finishedAt;
  final num? elapsedSeconds;
  final int candidateCount;
  final int previewReady;
  final int missingPreview;
  final int pendingReviewableCount;
  final String nextAction;
  final String latestError;
  final String warningMessage;

  factory CutsAnalyticsLatestSearch.fromJson(Map<String, dynamic> json) {
    return CutsAnalyticsLatestSearch(
      runId: _string(json['run_id']),
      status: _string(json['status']),
      startedAt: _string(json['started_at']),
      finishedAt: _string(json['finished_at']),
      elapsedSeconds: _num(json['elapsed_seconds']),
      candidateCount: _int(json['candidate_count']),
      previewReady: _int(json['preview_ready']),
      missingPreview: _int(json['missing_preview']),
      pendingReviewableCount: _int(json['pending_reviewable_count']),
      nextAction: _string(json['next_action']),
      latestError: _string(json['latest_error']),
      warningMessage: _string(json['warning_message']),
    );
  }
}

class CutsAnalyticsCache {
  const CutsAnalyticsCache({
    required this.totalVideosCached,
    required this.readyCount,
    required this.partialCount,
    required this.invalidCount,
    required this.staleCount,
    required this.transcriptCachedCount,
    required this.clipsCachedCount,
    required this.previewsCachedCount,
    required this.finalsCachedCount,
    required this.cacheHitsLatestRun,
    required this.cacheMissesLatestRun,
    required this.cachePartialsLatestRun,
    required this.cacheBypassedLatestRun,
    required this.videosReusedLatestRun,
    required this.videosProcessedFromScratchLatestRun,
    required this.estimatedSecondsSavedLatestRun,
    required this.duplicateCandidatesDetectedLatestRun,
    required this.duplicatePostsDetected,
    required this.approvedMissingFinals,
    required this.orphanFinals,
    required this.orphanPosts,
  });

  final int totalVideosCached;
  final int readyCount;
  final int partialCount;
  final int invalidCount;
  final int staleCount;
  final int transcriptCachedCount;
  final int clipsCachedCount;
  final int previewsCachedCount;
  final int finalsCachedCount;
  final int cacheHitsLatestRun;
  final int cacheMissesLatestRun;
  final int cachePartialsLatestRun;
  final int cacheBypassedLatestRun;
  final int videosReusedLatestRun;
  final int videosProcessedFromScratchLatestRun;
  final num? estimatedSecondsSavedLatestRun;
  final int duplicateCandidatesDetectedLatestRun;
  final int duplicatePostsDetected;
  final int approvedMissingFinals;
  final int orphanFinals;
  final int orphanPosts;

  factory CutsAnalyticsCache.fromJson(Map<String, dynamic> json) {
    return CutsAnalyticsCache(
      totalVideosCached: _int(json['total_videos_cached']),
      readyCount: _int(json['ready_count']),
      partialCount: _int(json['partial_count']),
      invalidCount: _int(json['invalid_count']),
      staleCount: _int(json['stale_count']),
      transcriptCachedCount: _int(json['transcript_cached_count']),
      clipsCachedCount: _int(json['clips_cached_count']),
      previewsCachedCount: _int(json['previews_cached_count']),
      finalsCachedCount: _int(json['finals_cached_count']),
      cacheHitsLatestRun: _int(json['cache_hits_latest_run']),
      cacheMissesLatestRun: _int(json['cache_misses_latest_run']),
      cachePartialsLatestRun: _int(json['cache_partials_latest_run']),
      cacheBypassedLatestRun: _int(json['cache_bypassed_latest_run']),
      videosReusedLatestRun: _int(json['videos_reused_latest_run']),
      videosProcessedFromScratchLatestRun: _int(
        json['videos_processed_from_scratch_latest_run'],
      ),
      estimatedSecondsSavedLatestRun: _num(
        json['estimated_seconds_saved_latest_run'],
      ),
      duplicateCandidatesDetectedLatestRun: _int(
        json['duplicate_candidates_detected_latest_run'],
      ),
      duplicatePostsDetected: _int(json['duplicate_posts_detected']),
      approvedMissingFinals: _int(json['approved_missing_finals']),
      orphanFinals: _int(json['orphan_finals']),
      orphanPosts: _int(json['orphan_posts']),
    );
  }
}

class CutsAnalyticsSourceIntelligence {
  const CutsAnalyticsSourceIntelligence({
    required this.latestDiscoveredCount,
    required this.latestAcceptedCount,
    required this.latestRejectedCount,
    required this.latestHardRejectedCount,
    required this.latestSoftRejectedCount,
    required this.latestFallbackUsed,
    required this.latestFallbackSelectedCount,
    required this.latestRejectedByReason,
    required this.latestAverageSourceScore,
    required this.latestSelectedVideoIds,
    required this.bestChannelsByApprovalRate,
    required this.bestQueriesByApprovalRate,
    required this.worstRejectionReasons,
  });

  final int latestDiscoveredCount;
  final int latestAcceptedCount;
  final int latestRejectedCount;
  final int latestHardRejectedCount;
  final int latestSoftRejectedCount;
  final bool latestFallbackUsed;
  final int latestFallbackSelectedCount;
  final Map<String, int> latestRejectedByReason;
  final num latestAverageSourceScore;
  final List<String> latestSelectedVideoIds;
  final List<Map<String, dynamic>> bestChannelsByApprovalRate;
  final List<Map<String, dynamic>> bestQueriesByApprovalRate;
  final List<Map<String, dynamic>> worstRejectionReasons;

  factory CutsAnalyticsSourceIntelligence.fromJson(Map<String, dynamic> json) {
    return CutsAnalyticsSourceIntelligence(
      latestDiscoveredCount: _int(json['latest_discovered_count']),
      latestAcceptedCount: _int(json['latest_accepted_count']),
      latestRejectedCount: _int(json['latest_rejected_count']),
      latestHardRejectedCount: _int(json['latest_hard_rejected_count']),
      latestSoftRejectedCount: _int(json['latest_soft_rejected_count']),
      latestFallbackUsed: _bool(json['latest_fallback_used']),
      latestFallbackSelectedCount: _int(json['latest_fallback_selected_count']),
      latestRejectedByReason: _intMap(json['latest_rejected_by_reason']),
      latestAverageSourceScore: _num(json['latest_average_source_score']) ?? 0,
      latestSelectedVideoIds: _stringList(json['latest_selected_video_ids']),
      bestChannelsByApprovalRate: _list(json['best_channels_by_approval_rate']),
      bestQueriesByApprovalRate: _list(json['best_queries_by_approval_rate']),
      worstRejectionReasons: _list(json['worst_rejection_reasons']),
    );
  }
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return value.map((key, item) => MapEntry('$key', item));
  return <String, dynamic>{};
}

List<Map<String, dynamic>> _list(Object? value) {
  if (value is! List) return const [];
  return value.map(_map).toList();
}

List<String> _stringList(Object? value) {
  if (value is! List) return const [];
  return value.map((item) => item.toString()).toList();
}

Map<String, int> _intMap(Object? value) {
  final map = _map(value);
  return map.map((key, item) => MapEntry(key, _int(item)));
}

String _string(Object? value) => value?.toString() ?? '';

int _int(Object? value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

double _double(Object? value) => _num(value)?.toDouble() ?? 0;

bool _bool(Object? value) {
  if (value is bool) return value;
  final text = value?.toString().toLowerCase();
  return text == 'true' || text == '1' || text == 'yes';
}

num? _num(Object? value) {
  if (value is num) return value;
  return num.tryParse(value?.toString() ?? '');
}
