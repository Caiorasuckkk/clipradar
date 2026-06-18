// Models for the background render pipeline (Bloco B/C).
//
// A [GenerationJob] mirrors a row of the backend SQLite job queue; a
// [GenerationRenderStatus] is what `GET /render/status` returns: the project's
// render fields plus the latest render job.

import 'generation_project.dart';

/// Result of `POST /render/prepare`: which prerequisites were fixed and which
/// blockers remain before a render can start.
class GenerationRenderPrepare {
  const GenerationRenderPrepare({
    required this.projectId,
    required this.readyForRender,
    required this.missing,
    required this.fixed,
    required this.withoutMediaCount,
    required this.pexelsDownloadedCount,
    required this.fallbackVisualCount,
    required this.mediaCount,
    required this.pexelsAvailable,
    required this.project,
  });

  final String projectId;
  final bool readyForRender;
  final List<String> missing;
  final List<String> fixed;
  final int withoutMediaCount;
  final int pexelsDownloadedCount;
  final int fallbackVisualCount;
  final int mediaCount;
  final bool pexelsAvailable;
  final GenerationProject? project;

  factory GenerationRenderPrepare.fromJson(Map<String, dynamic> json) {
    final projectJson = json['project'];
    return GenerationRenderPrepare(
      projectId: json['project_id']?.toString() ?? '',
      readyForRender: json['ready_for_render'] == true,
      missing: (json['missing'] as List<dynamic>? ?? [])
          .map((e) => e.toString())
          .toList(),
      fixed: (json['fixed'] as List<dynamic>? ?? [])
          .map((e) => e.toString())
          .toList(),
      withoutMediaCount: _toInt(json['visual_items_without_media_count']),
      pexelsDownloadedCount: _toInt(json['pexels_downloaded_count']),
      fallbackVisualCount: _toInt(json['fallback_visual_count']),
      mediaCount: _toInt(json['visual_media_count']),
      pexelsAvailable: json['pexels_available'] == true,
      project: projectJson is Map<String, dynamic>
          ? GenerationProject.fromJson(projectJson)
          : null,
    );
  }
}

class GenerationJob {
  const GenerationJob({
    required this.id,
    required this.type,
    required this.status,
    required this.progress,
    required this.step,
    required this.error,
    required this.attempts,
    required this.maxAttempts,
  });

  final String id;
  final String type;
  final String status; // queued | running | success | failed | cancelled
  final double progress; // 0.0 .. 1.0
  final String step;
  final String error;
  final int attempts;
  final int maxAttempts;

  bool get isTerminal =>
      status == 'success' || status == 'failed' || status == 'cancelled';
  bool get isActive => status == 'queued' || status == 'running';

  factory GenerationJob.fromJson(Map<String, dynamic> json) {
    return GenerationJob(
      id: json['id']?.toString() ?? '',
      type: json['type']?.toString() ?? '',
      status: json['status']?.toString() ?? 'queued',
      progress: _toDouble(json['progress']),
      step: json['step']?.toString() ?? '',
      error: json['error']?.toString() ?? '',
      attempts: _toInt(json['attempts']),
      maxAttempts: _toInt(json['max_attempts']),
    );
  }
}

class GenerationRenderStatus {
  const GenerationRenderStatus({
    required this.projectId,
    required this.renderStatus,
    required this.renderVideoUrl,
    required this.renderThumbnailUrl,
    required this.durationSeconds,
    required this.segmentCount,
    required this.error,
    required this.generatedAt,
    required this.visualFallbackUsed,
    required this.narrationStyleLabel,
    required this.captionCount,
    required this.wordCount,
    required this.wordsSource,
    required this.visualMediaCount,
    required this.visualItemCount,
    required this.job,
  });

  final String projectId;
  final String renderStatus; // none | queued | rendering | ready | failed | cancelled
  final String renderVideoUrl;
  final String renderThumbnailUrl;
  final double? durationSeconds;
  final int? segmentCount;
  final String error;
  final String generatedAt;
  final bool visualFallbackUsed;
  final String narrationStyleLabel;
  final int captionCount;
  final int wordCount;
  final String wordsSource;
  final int visualMediaCount;
  final int visualItemCount;
  final GenerationJob? job;

  bool get isReady => renderStatus == 'ready';
  bool get isStale => renderStatus == 'stale';
  bool get isWorking =>
      renderStatus == 'queued' ||
      renderStatus == 'rendering' ||
      (job?.isActive ?? false);

  /// Best-effort progress for the UI: queued shows a small baseline so the bar
  /// never looks stuck at zero before the worker picks the job up.
  double get progress {
    if (isReady) return 1.0;
    final jobProgress = job?.progress ?? 0.0;
    if (renderStatus == 'queued' && jobProgress <= 0) return 0.03;
    return jobProgress;
  }

  factory GenerationRenderStatus.fromJson(Map<String, dynamic> json) {
    final jobJson = json['job'];
    return GenerationRenderStatus(
      projectId: json['project_id']?.toString() ?? '',
      renderStatus: json['render_status']?.toString() ?? 'none',
      renderVideoUrl: json['render_video_url']?.toString() ?? '',
      renderThumbnailUrl: json['render_thumbnail_url']?.toString() ?? '',
      durationSeconds: _toDoubleOrNull(json['render_duration_seconds']),
      segmentCount: _toIntOrNull(json['render_segment_count']),
      error: json['render_error']?.toString() ?? '',
      generatedAt: json['render_generated_at']?.toString() ?? '',
      visualFallbackUsed: json['visual_fallback_used'] == true,
      narrationStyleLabel: json['narration_style_label']?.toString() ?? '',
      captionCount: _toInt(json['voice_caption_count']),
      wordCount: _toInt(json['voice_word_count']),
      wordsSource: json['voice_words_source']?.toString() ?? '',
      visualMediaCount: _toInt(json['visual_media_count']),
      visualItemCount: _toInt(json['visual_item_count']),
      job: jobJson is Map<String, dynamic>
          ? GenerationJob.fromJson(jobJson)
          : null,
    );
  }
}

double _toDouble(Object? value) {
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '') ?? 0.0;
}

double? _toDoubleOrNull(Object? value) {
  if (value == null) return null;
  if (value is num) return value.toDouble();
  return double.tryParse(value.toString());
}

int _toInt(Object? value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

int? _toIntOrNull(Object? value) {
  if (value == null) return null;
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value.toString());
}
