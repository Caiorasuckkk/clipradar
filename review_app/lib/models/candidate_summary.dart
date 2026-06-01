class CandidateSummary {
  const CandidateSummary({
    required this.totalCandidates,
    required this.previewReady,
    required this.missingPreview,
    required this.reviewed,
    required this.pending,
    required this.approved,
    required this.rejected,
    required this.needsAdjustment,
    required this.averageRating,
  });

  final int totalCandidates;
  final int previewReady;
  final int missingPreview;
  final int reviewed;
  final int pending;
  final int approved;
  final int rejected;
  final int needsAdjustment;
  final num? averageRating;

  factory CandidateSummary.fromJson(Map<String, dynamic> json) {
    return CandidateSummary(
      totalCandidates: _int(json['total_candidates']),
      previewReady: _int(json['preview_ready']),
      missingPreview: _int(json['missing_preview']),
      reviewed: _int(json['reviewed']),
      pending: _int(json['pending']),
      approved: _int(json['approved']),
      rejected: _int(json['rejected']),
      needsAdjustment: _int(json['needs_adjustment']),
      averageRating: _num(json['average_rating']),
    );
  }

  static int _int(Object? value) =>
      value is int ? value : int.tryParse(value?.toString() ?? '') ?? 0;
  static num? _num(Object? value) =>
      value is num ? value : num.tryParse(value?.toString() ?? '');
}
