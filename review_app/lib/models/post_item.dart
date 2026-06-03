class PostItem {
  const PostItem({
    required this.postId,
    required this.finalClipId,
    required this.clipId,
    required this.videoId,
    required this.videoTitle,
    required this.originalYoutubeUrl,
    required this.packageVideoFilename,
    required this.packageVideoPath,
    required this.durationSeconds,
    required this.finalReviewRating,
    required this.finalReviewReason,
    required this.finalReviewNotes,
    required this.suggestedTitle,
    required this.suggestedDescription,
    required this.suggestedHashtags,
    required this.postedStatus,
    required this.postedAt,
    required this.postedPlatforms,
    required this.postUrl,
    required this.notes,
  });

  final String postId;
  final String finalClipId;
  final String clipId;
  final String videoId;
  final String videoTitle;
  final String originalYoutubeUrl;
  final String packageVideoFilename;
  final String packageVideoPath;
  final num? durationSeconds;
  final num? finalReviewRating;
  final String finalReviewReason;
  final String finalReviewNotes;
  final String suggestedTitle;
  final String suggestedDescription;
  final List<String> suggestedHashtags;
  final String postedStatus;
  final String postedAt;
  final List<String> postedPlatforms;
  final String postUrl;
  final String notes;

  factory PostItem.fromJson(Map<String, dynamic> json) {
    return PostItem(
      postId: _string(json['post_id']),
      finalClipId: _string(json['final_clip_id']),
      clipId: _string(json['clip_id']),
      videoId: _string(json['video_id']),
      videoTitle: _string(json['video_title']),
      originalYoutubeUrl: _string(json['original_youtube_url']),
      packageVideoFilename: _string(json['package_video_filename']),
      packageVideoPath: _string(json['package_video_path']),
      durationSeconds: _num(json['duration_seconds']),
      finalReviewRating: _num(json['final_review_rating']),
      finalReviewReason: _string(json['final_review_reason']),
      finalReviewNotes: _string(json['final_review_notes']),
      suggestedTitle: _string(json['suggested_title']),
      suggestedDescription: _string(json['suggested_description']),
      suggestedHashtags: _stringList(json['suggested_hashtags']),
      postedStatus: _string(json['posted_status']),
      postedAt: _string(json['posted_at']),
      postedPlatforms: _stringList(json['posted_platforms']),
      postUrl: _string(json['post_url']),
      notes: _string(json['notes']),
    );
  }

  String get hashtagsText => suggestedHashtags.join(' ');

  static String _string(Object? value) => value?.toString() ?? '';

  static num? _num(Object? value) {
    if (value is num) return value;
    return num.tryParse(value?.toString() ?? '');
  }

  static List<String> _stringList(Object? value) {
    if (value is! List) return const [];
    return value.map((item) => item.toString()).toList();
  }
}
