import 'package:flutter/material.dart';

import '../models/review_clip.dart';

class ReviewedClipsScreen extends StatelessWidget {
  const ReviewedClipsScreen({
    super.key,
    required this.clips,
    required this.emptyTitle,
    required this.onClipTap,
  });

  final List<ReviewClip> clips;
  final String emptyTitle;
  final ValueChanged<ReviewClip> onClipTap;

  @override
  Widget build(BuildContext context) {
    if (clips.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.inbox_rounded,
                color: Color(0xFF00C8F0),
                size: 44,
              ),
              const SizedBox(height: 12),
              Text(
                emptyTitle,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Color(0xFFE8EAF0),
                  fontWeight: FontWeight.w800,
                  fontSize: 18,
                ),
              ),
            ],
          ),
        ),
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 18),
      itemCount: clips.length,
      separatorBuilder: (_, _) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final clip = clips[index];
        final review = clip.currentReview;
        return InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () => onClipTap(clip),
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: const Color(0xFF0F1018),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.white.withValues(alpha: 0.07)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    _StatusDot(status: review?.status),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        clip.videoTitle.isEmpty ? clip.clipId : clip.videoTitle,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Color(0xFFE8EAF0),
                          fontWeight: FontWeight.w800,
                          height: 1.2,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 9),
                Text(
                  clip.clipId,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Color(0xFF00C8F0),
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    _Pill('rating ${review?.rating ?? '-'}'),
                    _Pill(
                      review?.reason.isNotEmpty == true ? review!.reason : '-',
                    ),
                    _Pill(review?.status ?? 'pending'),
                    if (review?.reviewedAt.isNotEmpty == true)
                      _Pill(review!.reviewedAt.replaceFirst('T', ' ')),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _StatusDot extends StatelessWidget {
  const _StatusDot({required this.status});

  final String? status;

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      'approved' => const Color(0xFF10B981),
      'needs_adjustment' => const Color(0xFFF59E0B),
      'rejected' => const Color(0xFFEF4444),
      _ => const Color(0xFF6B7280),
    };
    return Container(
      width: 10,
      height: 10,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1C28),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Text(
        text,
        style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 11),
      ),
    );
  }
}
