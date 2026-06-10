class CandidateClip {
  const CandidateClip({
    required this.candidateId,
    required this.videoId,
    required this.videoTitle,
    required this.sourceCollection,
    required this.rank,
    required this.startSeconds,
    required this.endSeconds,
    required this.durationSeconds,
    required this.reason,
    required this.score,
    required this.qualityScore,
    required this.qualityTier,
    required this.positiveSignals,
    required this.negativeSignals,
    required this.rankingQualityScore,
    required this.rankingQualityTier,
    required this.sourceQualityScore,
    required this.sourceQualityTier,
    required this.riskLabel,
    required this.text,
    required this.youtubeUrl,
    required this.outputPreviewFilename,
    required this.previewExists,
    required this.previewMissing,
    required this.previewInvalid,
    required this.previewUrl,
    required this.alreadyReviewed,
    required this.currentReview,
  });

  final String candidateId;
  final String videoId;
  final String videoTitle;
  final String sourceCollection;
  final int? rank;
  final num? startSeconds;
  final num? endSeconds;
  final num? durationSeconds;
  final String reason;
  final num? score;
  final num? qualityScore;
  final String qualityTier;
  final List<String> positiveSignals;
  final List<String> negativeSignals;
  final num? rankingQualityScore;
  final String rankingQualityTier;
  final num? sourceQualityScore;
  final String sourceQualityTier;
  final String riskLabel;
  final String text;
  final String youtubeUrl;
  final String outputPreviewFilename;
  final bool previewExists;
  final bool previewMissing;
  final bool previewInvalid;
  final String previewUrl;
  final bool alreadyReviewed;
  final CandidateReview? currentReview;

  CandidateClip copyWith({
    bool? alreadyReviewed,
    CandidateReview? currentReview,
  }) {
    return CandidateClip(
      candidateId: candidateId,
      videoId: videoId,
      videoTitle: videoTitle,
      sourceCollection: sourceCollection,
      rank: rank,
      startSeconds: startSeconds,
      endSeconds: endSeconds,
      durationSeconds: durationSeconds,
      reason: reason,
      score: score,
      qualityScore: qualityScore,
      qualityTier: qualityTier,
      positiveSignals: positiveSignals,
      negativeSignals: negativeSignals,
      rankingQualityScore: rankingQualityScore,
      rankingQualityTier: rankingQualityTier,
      sourceQualityScore: sourceQualityScore,
      sourceQualityTier: sourceQualityTier,
      riskLabel: riskLabel,
      text: text,
      youtubeUrl: youtubeUrl,
      outputPreviewFilename: outputPreviewFilename,
      previewExists: previewExists,
      previewMissing: previewMissing,
      previewInvalid: previewInvalid,
      previewUrl: previewUrl,
      alreadyReviewed: alreadyReviewed ?? this.alreadyReviewed,
      currentReview: currentReview ?? this.currentReview,
    );
  }

  factory CandidateClip.fromJson(Map<String, dynamic> json) {
    return CandidateClip(
      candidateId: _string(json['candidate_id']),
      videoId: _string(json['video_id']),
      videoTitle: _string(json['video_title']),
      sourceCollection: _string(json['source_collection']),
      rank: _int(json['rank']),
      startSeconds:
          _num(json['final_start_seconds']) ?? _num(json['start_seconds']),
      endSeconds: _num(json['final_end_seconds']) ?? _num(json['end_seconds']),
      durationSeconds: _num(json['duration_seconds']),
      reason: _string(json['reason']),
      score: _num(json['score']),
      qualityScore:
          _num(json['candidate_quality_score']) ?? _num(json['quality_score']),
      qualityTier: _string(json['quality_tier']).isNotEmpty
          ? _string(json['quality_tier'])
          : _string(json['candidate_quality_tier']),
      positiveSignals: _stringList(
        json['positive_signals'] ?? json['quality_positive_signals'],
      ),
      negativeSignals: _stringList(
        json['negative_signals'] ?? json['quality_negative_signals'],
      ),
      rankingQualityScore: _num(json['ranking_quality_score']),
      rankingQualityTier: _string(json['ranking_quality_tier']),
      sourceQualityScore: _num(json['source_quality_score']),
      sourceQualityTier: _string(json['source_quality_tier']),
      riskLabel: _riskLabel(json),
      text: _string(json['text']),
      youtubeUrl: _string(json['youtube_url']),
      outputPreviewFilename: _string(json['output_preview_filename']),
      previewExists: json['preview_exists'] == true,
      previewMissing: json['preview_missing'] == true,
      previewInvalid: json['preview_invalid'] == true,
      previewUrl: _string(json['preview_url']),
      alreadyReviewed: json['already_reviewed'] == true,
      currentReview: json['current_candidate_review'] is Map<String, dynamic>
          ? CandidateReview.fromJson(
              json['current_candidate_review'] as Map<String, dynamic>,
            )
          : null,
    );
  }

  String get timeRange =>
      '${formatSeconds(startSeconds)} ate ${formatSeconds(endSeconds)}';

  static String formatSeconds(num? value) {
    final total = (value ?? 0).round().clamp(0, 999999);
    final minutes = total ~/ 60;
    final seconds = total % 60;
    return '$minutes:${seconds.toString().padLeft(2, '0')}';
  }

  static String _string(Object? value) => value?.toString() ?? '';
  static num? _num(Object? value) =>
      value is num ? value : num.tryParse(value?.toString() ?? '');
  static int? _int(Object? value) =>
      value is int ? value : int.tryParse(value?.toString() ?? '');

  static List<String> _stringList(Object? value) {
    if (value is! List) return const [];
    return value.map((item) => item.toString()).toList();
  }

  static String _riskLabel(Map<String, dynamic> json) {
    for (final key in const [
      'copyright_risk',
      'copyright_risk_tier',
      'copyright_risk_label',
      'risk_label',
      'sponsor_product_tier',
    ]) {
      final value = _string(json[key]).trim();
      if (value.isNotEmpty) return value;
    }
    final sponsorScore = _num(json['sponsor_product_score']);
    if (sponsorScore != null && sponsorScore > 0) {
      return 'produto ${sponsorScore.toStringAsFixed(1)}';
    }
    return '';
  }
}

class CandidateReview {
  const CandidateReview({
    required this.status,
    required this.rating,
    required this.reason,
    required this.notes,
  });

  final String status;
  final int? rating;
  final String reason;
  final String notes;

  factory CandidateReview.fromJson(Map<String, dynamic> json) {
    return CandidateReview(
      status: json['status']?.toString() ?? '',
      rating: CandidateClip._int(json['rating']),
      reason: json['reason']?.toString() ?? '',
      notes: json['notes']?.toString() ?? '',
    );
  }
}
