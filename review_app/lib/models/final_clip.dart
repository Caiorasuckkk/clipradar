class FinalClip {
  const FinalClip({
    required this.finalClipId,
    required this.clipId,
    required this.videoId,
    required this.videoTitle,
    required this.originalYoutubeUrl,
    required this.finalFilename,
    required this.finalUrlLocal,
    required this.rank,
    required this.rating,
    required this.reason,
    required this.reviewStatus,
    required this.reviewRating,
    required this.reviewReason,
    required this.reviewNotes,
    required this.startSeconds,
    required this.endSeconds,
    required this.durationSeconds,
    required this.finalDurationSeconds,
    required this.readyToPost,
    required this.postStatus,
    required this.alreadyReviewed,
    required this.currentFinalReview,
  });

  final String finalClipId;
  final String clipId;
  final String videoId;
  final String videoTitle;
  final String originalYoutubeUrl;
  final String finalFilename;
  final String finalUrlLocal;
  final int? rank;
  final num? rating;
  final String reason;
  final String reviewStatus;
  final num? reviewRating;
  final String reviewReason;
  final String reviewNotes;
  final num? startSeconds;
  final num? endSeconds;
  final num? durationSeconds;
  final num? finalDurationSeconds;
  final bool readyToPost;
  final String postStatus;
  final bool alreadyReviewed;
  final FinalReview? currentFinalReview;

  factory FinalClip.fromJson(Map<String, dynamic> json) {
    return FinalClip(
      finalClipId: _string(json['final_clip_id']),
      clipId: _string(json['clip_id']),
      videoId: _string(json['video_id']),
      videoTitle: _string(json['video_title']),
      originalYoutubeUrl: _string(json['original_youtube_url']),
      finalFilename: _string(json['final_filename']),
      finalUrlLocal: _string(json['final_url_local']),
      rank: _int(json['rank']),
      rating: _num(json['rating']),
      reason: _string(json['reason']),
      reviewStatus: _string(json['review_status']),
      reviewRating: _num(json['review_rating']),
      reviewReason: _string(json['review_reason']),
      reviewNotes: _string(json['review_notes']),
      startSeconds: _num(json['start_seconds']),
      endSeconds: _num(json['end_seconds']),
      durationSeconds: _num(json['duration_seconds']),
      finalDurationSeconds: _num(json['final_duration_seconds']),
      readyToPost: json['ready_to_post'] == true,
      postStatus: _string(json['post_status']),
      alreadyReviewed: json['already_reviewed'] == true,
      currentFinalReview: json['current_final_review'] is Map<String, dynamic>
          ? FinalReview.fromJson(
              json['current_final_review'] as Map<String, dynamic>,
            )
          : null,
    );
  }

  String get timeRange {
    return '${formatSeconds(startSeconds)} ate ${formatSeconds(endSeconds)}';
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

class FinalReview {
  const FinalReview({
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

  factory FinalReview.fromJson(Map<String, dynamic> json) {
    return FinalReview(
      status: json['status']?.toString() ?? '',
      rating: FinalClip._int(json['rating']),
      reason: json['reason']?.toString() ?? '',
      notes: json['notes']?.toString() ?? '',
      reviewedAt: json['reviewed_at']?.toString() ?? '',
      updatedAt: json['updated_at']?.toString(),
    );
  }
}
