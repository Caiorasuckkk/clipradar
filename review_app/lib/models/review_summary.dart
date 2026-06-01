class ReviewSummary {
  const ReviewSummary({
    required this.totalExported,
    required this.totalReviewed,
    required this.pending,
    required this.approved,
    required this.rejected,
    required this.needsAdjustment,
    required this.averageRating,
  });

  final int totalExported;
  final int totalReviewed;
  final int pending;
  final int approved;
  final int rejected;
  final int needsAdjustment;
  final num? averageRating;

  factory ReviewSummary.fromJson(Map<String, dynamic> json) {
    return ReviewSummary(
      totalExported: _int(json['total_exported']),
      totalReviewed: _int(json['total_reviewed']),
      pending: _int(json['pending']),
      approved: _int(json['approved']),
      rejected: _int(json['rejected']),
      needsAdjustment: _int(json['needs_adjustment']),
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
