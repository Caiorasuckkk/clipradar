class FinalSummary {
  const FinalSummary({
    required this.totalFinal,
    required this.reviewed,
    required this.pending,
    required this.readyToPost,
    required this.doNotPost,
    required this.needsEdit,
    required this.averageRating,
  });

  final int totalFinal;
  final int reviewed;
  final int pending;
  final int readyToPost;
  final int doNotPost;
  final int needsEdit;
  final num? averageRating;

  factory FinalSummary.fromJson(Map<String, dynamic> json) {
    return FinalSummary(
      totalFinal: _int(json['total_final']),
      reviewed: _int(json['reviewed']),
      pending: _int(json['pending']),
      readyToPost: _int(json['ready_to_post']),
      doNotPost: _int(json['do_not_post']),
      needsEdit: _int(json['needs_edit']),
      averageRating: _num(json['average_rating']),
    );
  }

  static int _int(Object? value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    return int.tryParse(value?.toString() ?? '') ?? 0;
  }

  static num? _num(Object? value) {
    if (value is num) return value;
    return num.tryParse(value?.toString() ?? '');
  }
}
