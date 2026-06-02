class JobRun {
  const JobRun({
    required this.runId,
    required this.jobKey,
    required this.status,
    required this.stdoutTail,
    required this.stderrTail,
    required this.exitCode,
    required this.elapsedSeconds,
  });

  final String runId;
  final String jobKey;
  final String status;
  final String stdoutTail;
  final String stderrTail;
  final int? exitCode;
  final num? elapsedSeconds;

  bool get isRunning => status == 'queued' || status == 'running';

  factory JobRun.fromJson(Map<String, dynamic> json) {
    return JobRun(
      runId: _string(json['run_id']),
      jobKey: _string(json['job_key']),
      status: _string(json['status']),
      stdoutTail: _string(json['stdout_tail']),
      stderrTail: _string(json['stderr_tail']),
      exitCode: _int(json['exit_code']),
      elapsedSeconds: _num(json['elapsed_seconds']),
    );
  }

  static String _string(Object? value) => value?.toString() ?? '';
  static int? _int(Object? value) =>
      value is int ? value : int.tryParse(value?.toString() ?? '');
  static num? _num(Object? value) =>
      value is num ? value : num.tryParse(value?.toString() ?? '');
}
