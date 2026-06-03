class PostsSummary {
  const PostsSummary({
    required this.total,
    required this.notPosted,
    required this.posted,
    required this.scheduled,
    required this.doNotPost,
  });

  final int total;
  final int notPosted;
  final int posted;
  final int scheduled;
  final int doNotPost;

  factory PostsSummary.fromJson(Map<String, dynamic> json) {
    return PostsSummary(
      total: _int(json['total']),
      notPosted: _int(json['not_posted']),
      posted: _int(json['posted']),
      scheduled: _int(json['scheduled']),
      doNotPost: _int(json['do_not_post']),
    );
  }

  static int _int(Object? value) =>
      value is int ? value : int.tryParse(value?.toString() ?? '') ?? 0;
}
