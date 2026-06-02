class OpsStatus {
  const OpsStatus({
    required this.totalCandidates,
    required this.previewReady,
    required this.missingPreview,
    required this.candidateReviewsPending,
    required this.candidateApproved,
    required this.finalReviewsPending,
    required this.readyToPost,
    required this.failedDownloads,
    required this.latestPackage,
  });

  final int totalCandidates;
  final int previewReady;
  final int missingPreview;
  final int candidateReviewsPending;
  final int candidateApproved;
  final int finalReviewsPending;
  final int readyToPost;
  final int failedDownloads;
  final String latestPackage;

  factory OpsStatus.fromJson(Map<String, dynamic> json) {
    final candidate = _map(json['candidate_queue']);
    final finalReviews = _map(json['final_reviews']);
    final failed = _map(json['failed_downloads']);
    final package = _map(json['posting_package']);
    return OpsStatus(
      totalCandidates: _int(candidate['total_candidates']),
      previewReady: _int(candidate['preview_ready']),
      missingPreview: _int(candidate['missing_preview']),
      candidateReviewsPending: _int(candidate['reviews_pending']),
      candidateApproved: _int(candidate['approved']),
      finalReviewsPending: _int(finalReviews['pending']),
      readyToPost: _int(finalReviews['ready_to_post']),
      failedDownloads: _int(failed['count']),
      latestPackage: _string(package['path']),
    );
  }

  static Map<String, dynamic> _map(Object? value) =>
      value is Map<String, dynamic> ? value : <String, dynamic>{};
  static int _int(Object? value) =>
      value is int ? value : int.tryParse(value?.toString() ?? '') ?? 0;
  static String _string(Object? value) => value?.toString() ?? '';
}
