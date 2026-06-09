class JobRun {
  const JobRun({
    required this.runId,
    required this.jobKey,
    required this.status,
    required this.stdoutTail,
    required this.stderrTail,
    required this.exitCode,
    required this.elapsedSeconds,
    required this.pid,
    required this.startedAt,
    required this.command,
    required this.latestError,
    required this.warningMessage,
    required this.candidateCount,
    required this.previewReady,
    required this.missingPreview,
    required this.pendingReviewableCount,
    required this.nextAction,
    required this.partialReviewable,
    required this.partialCandidateCount,
    required this.partialPreviewReady,
    required this.partialPendingReviewableCount,
    required this.currentVideoId,
    required this.currentVideoIndex,
    required this.totalVideos,
    required this.currentStepDetail,
  });

  final String runId;
  final String jobKey;
  final String status;
  final String stdoutTail;
  final String stderrTail;
  final int? exitCode;
  final num? elapsedSeconds;
  final int? pid;
  final String startedAt;
  final List<String> command;
  final String latestError;
  final String warningMessage;
  final int candidateCount;
  final int previewReady;
  final int missingPreview;
  final int pendingReviewableCount;
  final String nextAction;
  final bool partialReviewable;
  final int partialCandidateCount;
  final int partialPreviewReady;
  final int partialPendingReviewableCount;
  final String currentVideoId;
  final int? currentVideoIndex;
  final int? totalVideos;
  final String currentStepDetail;

  bool get isRunning => status == 'queued' || status == 'running';
  bool get isTerminal =>
      status == 'success' ||
      status == 'failed' ||
      status == 'cancelled' ||
      status == 'success_with_warnings';

  factory JobRun.fromJson(Map<String, dynamic> json) {
    return JobRun(
      runId: _string(json['run_id']),
      jobKey: _string(json['job_key']),
      status: _string(json['status']),
      stdoutTail: _string(json['stdout_tail']),
      stderrTail: _string(json['stderr_tail']),
      exitCode: _int(json['exit_code']),
      elapsedSeconds: _num(json['elapsed_seconds']),
      pid: _int(json['pid']),
      startedAt: _string(json['started_at']),
      command: (json['command'] as List<dynamic>? ?? [])
          .map((item) => item.toString())
          .toList(),
      latestError: _string(json['latest_error']),
      warningMessage: _string(json['warning_message']),
      candidateCount: _int(json['candidate_count']) ?? 0,
      previewReady: _int(json['preview_ready']) ?? 0,
      missingPreview: _int(json['missing_preview']) ?? 0,
      pendingReviewableCount: _int(json['pending_reviewable_count']) ?? 0,
      nextAction: _string(json['next_action']),
      partialReviewable: json['partial_reviewable'] == true,
      partialCandidateCount: _int(json['partial_candidate_count']) ?? 0,
      partialPreviewReady: _int(json['partial_preview_ready']) ?? 0,
      partialPendingReviewableCount:
          _int(json['partial_pending_reviewable_count']) ?? 0,
      currentVideoId: _string(json['current_video_id']),
      currentVideoIndex: _int(json['current_video_index']),
      totalVideos: _int(json['total_videos']),
      currentStepDetail: _string(json['current_step_detail']),
    );
  }

  static String _string(Object? value) => value?.toString() ?? '';
  static int? _int(Object? value) =>
      value is int ? value : int.tryParse(value?.toString() ?? '');
  static num? _num(Object? value) =>
      value is num ? value : num.tryParse(value?.toString() ?? '');
}
