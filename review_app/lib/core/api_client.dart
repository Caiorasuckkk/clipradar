import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/review_clip.dart';
import '../models/review_summary.dart';
import '../models/final_clip.dart';
import '../models/final_summary.dart';
import '../models/generation_project.dart';
import '../models/job_run.dart';
import '../models/ops_status.dart';
import '../models/candidate_clip.dart';
import '../models/candidate_summary.dart';
import '../models/cuts_analytics.dart';
import '../models/post_item.dart';
import '../models/posts_summary.dart';
import 'app_config.dart';

class ApiClient {
  ApiClient({http.Client? client, this.baseUrl = AppConfig.apiBaseUrl})
    : _client = client ?? http.Client();

  final http.Client _client;
  final String baseUrl;

  Uri _uri(String path, [Map<String, String>? query]) {
    return Uri.parse('$baseUrl$path').replace(queryParameters: query);
  }

  String exportUrl(String filename) => '$baseUrl/exports/$filename';

  String finalExportUrl(String filename) => '$baseUrl/final_exports/$filename';
  String candidatePreviewUrl(String filename) =>
      '$baseUrl/candidate_previews/$filename';
  String postingPackageVideoUrl(String filename) =>
      '$baseUrl/posting_package/latest/videos/$filename';
  String generationVoiceAudioUrl(String projectId) =>
      '$baseUrl/generation/projects/$projectId/voice/audio';

  Future<List<ReviewClip>> fetchClips({String status = 'all'}) async {
    final response = await _client.get(
      _uri('/review/clips', {'status': status}),
    );
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    final clips = payload['clips'] as List<dynamic>? ?? [];
    return clips
        .map((item) => ReviewClip.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<ReviewClip?> fetchNextClip() async {
    final response = await _client.get(_uri('/review/clips/next'));
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    final clip = payload['clip'];
    if (clip == null) return null;
    return ReviewClip.fromJson(clip as Map<String, dynamic>);
  }

  Future<ReviewSummary> fetchSummary() async {
    final response = await _client.get(_uri('/review/summary'));
    _throwIfBad(response);
    return ReviewSummary.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<void> saveReview({
    required String clipId,
    required String status,
    required int rating,
    required String reason,
    required String notes,
  }) async {
    final response = await _client.post(
      _uri('/review/clips/$clipId'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'status': status,
        'rating': rating,
        'reason': reason,
        'notes': notes,
        'ideal_start_seconds': null,
        'ideal_end_seconds': null,
      }),
    );
    _throwIfBad(response);
  }

  Future<List<FinalClip>> fetchFinalClips({String status = 'pending'}) async {
    final response = await _client.get(
      _uri('/final/clips', {'status': status}),
    );
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    final clips = payload['clips'] as List<dynamic>? ?? [];
    return clips
        .map((item) => FinalClip.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<FinalClip?> fetchNextFinalClip() async {
    final response = await _client.get(_uri('/final/clips/next'));
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    final clip = payload['clip'];
    if (clip == null) return null;
    return FinalClip.fromJson(clip as Map<String, dynamic>);
  }

  Future<FinalSummary> fetchFinalSummary() async {
    final response = await _client.get(_uri('/final/summary'));
    _throwIfBad(response);
    return FinalSummary.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<void> saveFinalReview({
    required String finalClipId,
    required String status,
    required int rating,
    required String reason,
    required String notes,
  }) async {
    final response = await _client.post(
      _uri('/final/clips/$finalClipId'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'status': status,
        'rating': rating,
        'reason': reason,
        'notes': notes,
      }),
    );
    _throwIfBad(response);
  }

  Future<List<CandidateClip>> fetchCandidateClips({
    String status = 'pending',
  }) async {
    final response = await _client.get(
      _uri('/candidate/clips', {'status': status}),
    );
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    final clips = payload['clips'] as List<dynamic>? ?? [];
    return clips
        .map((item) => CandidateClip.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<CandidateSummary> fetchCandidateSummary() async {
    final response = await _client.get(_uri('/candidate/summary'));
    _throwIfBad(response);
    return CandidateSummary.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<CandidateReviewSaveResult> saveCandidateReview({
    required String candidateId,
    required String status,
    required int rating,
    required String reason,
    required String notes,
  }) async {
    final response = await _client.post(
      _uri('/candidate/clips/$candidateId'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'status': status,
        'rating': rating,
        'reason': reason,
        'notes': notes,
        'ideal_start_seconds': null,
        'ideal_end_seconds': null,
      }),
    );
    _throwIfBad(response);
    return CandidateReviewSaveResult.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<void> cancelOpsJobRun(String runId) async {
    final response = await _client.post(_uri('/ops/jobs/runs/$runId/cancel'));
    _throwIfBad(response);
  }

  Future<ApprovedGenerationStatus> fetchApprovedGenerationStatus() async {
    final response = await _client.get(_uri('/generation/approved/status'));
    _throwIfBad(response);
    return ApprovedGenerationStatus.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<ApprovedGenerationStatus> triggerApprovedGeneration({
    String? candidateId,
    bool retryFailed = false,
  }) async {
    final response = await _client.post(
      _uri('/generation/approved/trigger'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'candidate_id': candidateId,
        'run_async': true,
        'retry_failed': retryFailed,
      }),
    );
    _throwIfBad(response);
    await Future<void>.delayed(const Duration(milliseconds: 150));
    return fetchApprovedGenerationStatus();
  }

  Future<List<GenerationIdea>> generateIdeas({
    required String niche,
    required String topic,
    required String language,
    required String tone,
  }) async {
    final response = await _client.post(
      _uri('/generation/ideas'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'niche': niche,
        'topic': topic,
        'language': language,
        'tone': tone,
      }),
    );
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    return (payload['ideas'] as List<dynamic>? ?? [])
        .map((item) => GenerationIdea.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<GenerationEngineStatus> fetchGenerationEngineStatus() async {
    final response = await _client.get(_uri('/generation/engine/status'));
    _throwIfBad(response);
    return GenerationEngineStatus.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationScript> generateScript({
    required String idea,
    required String niche,
    required int durationSeconds,
    required String tone,
    required String language,
  }) async {
    final response = await _client.post(
      _uri('/generation/scripts'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'idea': idea,
        'niche': niche,
        'duration_seconds': durationSeconds,
        'tone': tone,
        'language': language,
      }),
    );
    _throwIfBad(response);
    return GenerationScript.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<List<GenerationProject>> getGenerationProjects() async {
    final response = await _client.get(_uri('/generation/projects'));
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    return (payload['projects'] as List<dynamic>? ?? [])
        .map((item) => GenerationProject.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<GenerationProject> createGenerationProject(
    Map<String, dynamic> payload,
  ) async {
    final response = await _client.post(
      _uri('/generation/projects'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationProject> updateGenerationProject({
    required String projectId,
    required Map<String, dynamic> payload,
  }) async {
    final response = await _client.put(
      _uri('/generation/projects/$projectId'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationProject> runGenerationGuardrail(String projectId) async {
    final response = await _client.post(
      _uri('/generation/projects/$projectId/guardrail'),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<void> deleteGenerationProject(String projectId) async {
    final response = await _client.delete(
      _uri('/generation/projects/$projectId'),
    );
    _throwIfBad(response);
  }

  Future<GenerationVoicesResponse> getGenerationVoices() async {
    final response = await _client.get(_uri('/generation/voices'));
    _throwIfBad(response);
    return GenerationVoicesResponse.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationProject> generateProjectVoice({
    required String projectId,
    required String voice,
    required String rate,
    required String pitch,
  }) async {
    final response = await _client.post(
      _uri('/generation/projects/$projectId/voice'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'voice': voice, 'rate': rate, 'pitch': pitch}),
    );
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    return GenerationProject.fromJson(
      payload['project'] as Map<String, dynamic>,
    );
  }

  Future<GenerationProject> deleteProjectVoice(String projectId) async {
    final response = await _client.delete(
      _uri('/generation/projects/$projectId/voice'),
    );
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    return GenerationProject.fromJson(
      payload['project'] as Map<String, dynamic>,
    );
  }

  Future<OpsStatus> fetchOpsStatus() async {
    final response = await _client.get(_uri('/ops/status'));
    _throwIfBad(response);
    return OpsStatus.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<List<Map<String, dynamic>>> fetchOpsJobs() async {
    final response = await _client.get(_uri('/ops/jobs'));
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    return (payload['jobs'] as List<dynamic>? ?? [])
        .whereType<Map<String, dynamic>>()
        .toList();
  }

  Future<JobRun> startOpsJob({
    required String jobKey,
    Map<String, dynamic> params = const {},
  }) async {
    final result = await startOpsJobWithResult(jobKey: jobKey, params: params);
    return result.run;
  }

  Future<OpsJobStartResult> startOpsJobWithResult({
    required String jobKey,
    Map<String, dynamic> params = const {},
  }) async {
    final response = await _client.post(
      _uri('/ops/jobs/run'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'job_key': jobKey, 'params': params}),
    );
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    final run = await fetchOpsJobRun(payload['run_id'].toString());
    return OpsJobStartResult(
      run: run,
      alreadyRunning: payload['status']?.toString() == 'already_running',
      message: payload['message']?.toString() ?? '',
    );
  }

  Future<JobRun> fetchOpsJobRun(String runId) async {
    final response = await _client.get(_uri('/ops/jobs/runs/$runId'));
    _throwIfBad(response);
    return JobRun.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<JobRunLogs> fetchOpsJobRunLogs(String runId) async {
    final response = await _client.get(_uri('/ops/jobs/runs/$runId/logs'));
    _throwIfBad(response);
    return JobRunLogs.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<JobRun> fetchLatestOpsRun() async {
    final response = await _client.get(_uri('/ops/jobs/runs', {'limit': '1'}));
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    final runs = payload['runs'] as List<dynamic>? ?? [];
    if (runs.isEmpty) {
      return const JobRun(
        runId: '',
        jobKey: '',
        status: 'none',
        stdoutTail: '',
        stderrTail: '',
        exitCode: null,
        elapsedSeconds: null,
        pid: null,
        startedAt: '',
        command: [],
        latestError: '',
        warningMessage: '',
        candidateCount: 0,
        previewReady: 0,
        missingPreview: 0,
        pendingReviewableCount: 0,
        nextAction: '',
        partialReviewable: false,
        partialCandidateCount: 0,
        partialPreviewReady: 0,
        partialPendingReviewableCount: 0,
        currentVideoId: '',
        currentVideoIndex: null,
        totalVideos: null,
        currentStepDetail: '',
      );
    }
    return JobRun.fromJson(runs.first as Map<String, dynamic>);
  }

  Future<List<PostItem>> fetchPosts({String status = 'not_posted'}) async {
    final response = await _client.get(_uri('/posts', {'status': status}));
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    final posts = payload['posts'] as List<dynamic>? ?? [];
    return posts
        .map((item) => PostItem.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<PostsSummary> fetchPostsSummary() async {
    final response = await _client.get(_uri('/posts/summary'));
    _throwIfBad(response);
    return PostsSummary.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<CutsAnalytics> fetchCutsAnalytics() async {
    final response = await _client.get(_uri('/analytics/cuts/summary'));
    _throwIfBad(response);
    return CutsAnalytics.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<void> updatePostStatus({
    required String postId,
    required String status,
    required List<String> platforms,
    String postedAt = '',
    String postUrl = '',
    required String notes,
  }) async {
    final response = await _client.post(
      _uri('/posts/$postId'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'status': status,
        'platforms': platforms,
        'posted_at': postedAt,
        'post_url': postUrl,
        'notes': notes,
      }),
    );
    _throwIfBad(response);
  }

  void _throwIfBad(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) return;
    throw ApiException(
      'HTTP ${response.statusCode}: ${response.body}',
      statusCode: response.statusCode,
      body: response.body,
    );
  }
}

class OpsJobStartResult {
  const OpsJobStartResult({
    required this.run,
    required this.alreadyRunning,
    required this.message,
  });

  final JobRun run;
  final bool alreadyRunning;
  final String message;
}

class JobRunLogs {
  const JobRunLogs({
    required this.runId,
    required this.jobKey,
    required this.status,
    required this.pid,
    required this.startedAt,
    required this.elapsedSeconds,
    required this.command,
    required this.stdoutTail,
    required this.stderrTail,
  });

  final String runId;
  final String jobKey;
  final String status;
  final int? pid;
  final String startedAt;
  final num? elapsedSeconds;
  final List<String> command;
  final String stdoutTail;
  final String stderrTail;

  factory JobRunLogs.fromJson(Map<String, dynamic> json) {
    return JobRunLogs(
      runId: json['run_id']?.toString() ?? '',
      jobKey: json['job_key']?.toString() ?? '',
      status: json['status']?.toString() ?? '',
      pid: _intValueOrNull(json['pid']),
      startedAt: json['started_at']?.toString() ?? '',
      elapsedSeconds: json['elapsed_seconds'] is num
          ? json['elapsed_seconds'] as num
          : num.tryParse(json['elapsed_seconds']?.toString() ?? ''),
      command: (json['command'] as List<dynamic>? ?? [])
          .map((item) => item.toString())
          .toList(),
      stdoutTail: json['stdout_tail']?.toString() ?? '',
      stderrTail: json['stderr_tail']?.toString() ?? '',
    );
  }
}

class CandidateReviewSaveResult {
  const CandidateReviewSaveResult({
    required this.autoGenerationStatus,
    required this.autoGenerationMessage,
  });

  final String autoGenerationStatus;
  final String autoGenerationMessage;

  factory CandidateReviewSaveResult.fromJson(Map<String, dynamic> json) {
    return CandidateReviewSaveResult(
      autoGenerationStatus: json['auto_generation_status']?.toString() ?? '',
      autoGenerationMessage: json['auto_generation_message']?.toString() ?? '',
    );
  }
}

class ApprovedGenerationStatus {
  const ApprovedGenerationStatus({
    required this.running,
    required this.pendingCount,
    required this.generatedCount,
    required this.failedCount,
    required this.lastRunId,
    required this.latestError,
  });

  final bool running;
  final int pendingCount;
  final int generatedCount;
  final int failedCount;
  final String lastRunId;
  final String latestError;

  factory ApprovedGenerationStatus.fromJson(Map<String, dynamic> json) {
    return ApprovedGenerationStatus(
      running: json['running'] == true,
      pendingCount: _intValue(json['pending_count']),
      generatedCount: _intValue(json['generated_count']),
      failedCount: _intValue(json['failed_count']),
      lastRunId: json['last_run_id']?.toString() ?? '',
      latestError: json['latest_error']?.toString() ?? '',
    );
  }
}

int _intValue(Object? value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

int? _intValueOrNull(Object? value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '');
}

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode, this.body = ''});

  final String message;
  final int? statusCode;
  final String body;

  @override
  String toString() => message;
}
