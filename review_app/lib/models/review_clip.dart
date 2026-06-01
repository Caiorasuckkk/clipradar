class ReviewClip {
  const ReviewClip({
    required this.clipId,
    required this.videoId,
    required this.videoTitle,
    required this.rank,
    required this.reviewRating,
    required this.reviewReason,
    required this.sourceQualityScore,
    required this.sourceQualityTier,
    required this.startSeconds,
    required this.endSeconds,
    required this.finalStartSeconds,
    required this.finalEndSeconds,
    required this.durationSeconds,
    required this.youtubeUrl,
    required this.outputFilename,
    required this.videoUrl,
    required this.alreadyReviewed,
    required this.currentReview,
  });

  final String clipId;
  final String videoId;
  final String videoTitle;
  final int? rank;
  final num? reviewRating;
  final String reviewReason;
  final num? sourceQualityScore;
  final String? sourceQualityTier;
  final num? startSeconds;
  final num? endSeconds;
  final num? finalStartSeconds;
  final num? finalEndSeconds;
  final num? durationSeconds;
  final String youtubeUrl;
  final String outputFilename;
  final String videoUrl;
  final bool alreadyReviewed;
  final RenderedReview? currentReview;

  factory ReviewClip.fromJson(Map<String, dynamic> json) {
    return ReviewClip(
      clipId: _string(json['clip_id']),
      videoId: _string(json['video_id']),
      videoTitle: _string(json['video_title']),
      rank: _int(json['rank']),
      reviewRating: _num(json['review_rating']),
      reviewReason: _string(json['review_reason']),
      sourceQualityScore: _num(json['source_quality_score']),
      sourceQualityTier: json['source_quality_tier']?.toString(),
      startSeconds: _num(json['start_seconds']),
      endSeconds: _num(json['end_seconds']),
      finalStartSeconds: _num(json['final_start_seconds']),
      finalEndSeconds: _num(json['final_end_seconds']),
      durationSeconds: _num(json['duration_seconds']),
      youtubeUrl: _string(json['youtube_url']),
      outputFilename: _string(json['output_filename']),
      videoUrl: _string(json['video_url']),
      alreadyReviewed: json['already_reviewed'] == true,
      currentReview: json['current_review'] is Map<String, dynamic>
          ? RenderedReview.fromJson(
              json['current_review'] as Map<String, dynamic>,
            )
          : null,
    );
  }

  String get timeRange {
    return '${formatSeconds(finalStartSeconds ?? startSeconds)} ate ${formatSeconds(finalEndSeconds ?? endSeconds)}';
  }

  static String formatSeconds(num? value) {
    final total = (value ?? 0).round().clamp(0, 999999);
    final minutes = total ~/ 60;
    final seconds = total % 60;
    return '$minutes:${seconds.toString().padLeft(2, '0')}';
  }

  static String _string(Object? value) => value?.toString() ?? '';

  static num? _num(Object? value) {
    if (value is num) return value;
    return num.tryParse(value?.toString() ?? '');
  }

  static int? _int(Object? value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    return int.tryParse(value?.toString() ?? '');
  }
}

class RenderedReview {
  const RenderedReview({
    required this.status,
    required this.rating,
    required this.reason,
    required this.notes,
    required this.reviewedAt,
    required this.updatedAt,
  });

  final String status;
  final int? rating;
  final String reason;
  final String notes;
  final String reviewedAt;
  final String? updatedAt;

  factory RenderedReview.fromJson(Map<String, dynamic> json) {
    return RenderedReview(
      status: json['status']?.toString() ?? '',
      rating: ReviewClip._int(json['rating']),
      reason: json['reason']?.toString() ?? '',
      notes: json['notes']?.toString() ?? '',
      reviewedAt: json['reviewed_at']?.toString() ?? '',
      updatedAt: json['updated_at']?.toString(),
    );
  }
}
