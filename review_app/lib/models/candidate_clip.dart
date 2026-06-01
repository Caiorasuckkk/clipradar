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
    required this.youtubeUrl,
    required this.outputPreviewFilename,
    required this.previewExists,
    required this.previewMissing,
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
  final String youtubeUrl;
  final String outputPreviewFilename;
  final bool previewExists;
  final bool previewMissing;
  final String previewUrl;
  final bool alreadyReviewed;
  final CandidateReview? currentReview;

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
      youtubeUrl: _string(json['youtube_url']),
      outputPreviewFilename: _string(json['output_preview_filename']),
      previewExists: json['preview_exists'] == true,
      previewMissing: json['preview_missing'] == true,
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
