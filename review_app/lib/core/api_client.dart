import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/review_clip.dart';
import '../models/review_summary.dart';
import '../models/final_clip.dart';
import '../models/final_summary.dart';
import '../models/generation_project.dart';
import '../models/generation_render.dart';
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
    : _client = client ?? _AuthClient(http.Client());

  final http.Client _client;
  final String baseUrl;

  Uri _uri(String path, [Map<String, String>? query]) {
    return Uri.parse('$baseUrl$path').replace(queryParameters: query);
  }

  // Media URLs are opened directly by the video player / Image.network /
  // url_launcher, which don't go through _client — so the token rides as a
  // query param. No-op when the token is empty (local dev).
  String _withToken(String url) {
    if (AppConfig.apiToken.isEmpty) return url;
    final sep = url.contains('?') ? '&' : '?';
    return '$url${sep}token=${Uri.encodeComponent(AppConfig.apiToken)}';
  }

  String exportUrl(String filename) => _withToken('$baseUrl/exports/$filename');

  String finalExportUrl(String filename) =>
      _withToken('$baseUrl/final_exports/$filename');
  String candidatePreviewUrl(String filename) =>
      _withToken('$baseUrl/candidate_previews/$filename');
  String postingPackageVideoUrl(String filename) =>
      _withToken('$baseUrl/posting_package/latest/videos/$filename');
  String generationVoiceAudioUrl(String projectId) =>
      _withToken('$baseUrl/generation/projects/$projectId/voice/audio');
  String generationRenderVideoUrl(String projectId) =>
      _withToken('$baseUrl/generation/projects/$projectId/render/video');
  String generationRenderThumbnailUrl(String projectId) =>
      _withToken('$baseUrl/generation/projects/$projectId/render/thumbnail');

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
    String scriptDepth = 'normal',
    String narrativeStyle = 'dramatic',
    String contentFormat = 'manual_topic',
    String extraContext = '',
  }) async {
    final response = await _client.post(
      _uri('/generation/scripts'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'idea': idea,
        'topic': idea,
        'niche': niche,
        'duration_seconds': durationSeconds,
        'tone': tone,
        'language': language,
        'script_depth': scriptDepth,
        'narrative_style': narrativeStyle,
        'content_format': contentFormat,
        'extra_context': extraContext,
      }),
    );
    _throwIfBad(response);
    return GenerationScript.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationProject> regenerateGenerationProjectScript({
    required String projectId,
    required int durationSeconds,
    bool forceResearch = false,
    String provider = 'auto',
    String scriptDepth = 'normal',
    String narrativeStyle = 'dramatic',
  }) async {
    final response = await _client.post(
      _uri('/generation/projects/$projectId/script/regenerate'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'duration_seconds': durationSeconds,
        'force_research': forceResearch,
        'provider': provider,
        'script_depth': scriptDepth,
        'narrative_style': narrativeStyle,
      }),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationProject> improveGenerationProjectScript({
    required String projectId,
    required String scriptDepth,
    required String narrativeStyle,
    required int durationSeconds,
    bool preserveFacts = true,
    bool forceResearch = false,
  }) async {
    final response = await _client.post(
      _uri('/generation/projects/$projectId/script/improve'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'script_depth': scriptDepth,
        'narrative_style': narrativeStyle,
        'duration_seconds': durationSeconds,
        'preserve_facts': preserveFacts,
        'force_research': forceResearch,
      }),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationProject> regenerateGenerationProjectResearch({
    required String projectId,
    bool forceResearch = true,
    String provider = 'auto',
  }) async {
    final response = await _client.post(
      _uri('/generation/projects/$projectId/research/regenerate'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'force_research': forceResearch, 'provider': provider}),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
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

  Future<GenerationProject> createGenerationProjectFromIdea({
    required String idea,
    required String niche,
    required String language,
    required String tone,
    required int durationSeconds,
    String scriptDepth = 'normal',
    String narrativeStyle = 'dramatic',
    String contentFormat = 'manual_topic',
    String extraContext = '',
    bool autoGenerateScript = true,
    bool autoGenerateVoice = false,
    bool autoSuggestVisuals = false,
  }) async {
    final response = await _client.post(
      _uri('/generation/projects/from-idea'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'idea': idea,
        'niche': niche,
        'language': language,
        'tone': tone,
        'duration_seconds': durationSeconds,
        'script_depth': scriptDepth,
        'narrative_style': narrativeStyle,
        'content_format': contentFormat,
        'extra_context': extraContext,
        'auto_generate_script': autoGenerateScript,
        'auto_generate_voice': autoGenerateVoice,
        'auto_suggest_visuals': autoSuggestVisuals,
      }),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationProject> createGenerationProjectFromScript({
    required String script,
    required String title,
    required String niche,
    required String language,
    required String tone,
    required int durationSeconds,
    bool autoGenerateVoice = false,
    bool autoSuggestVisuals = true,
  }) async {
    final response = await _client.post(
      _uri('/generation/projects/from-script'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'script': script,
        'title': title,
        'niche': niche,
        'language': language,
        'tone': tone,
        'duration_seconds': durationSeconds,
        'auto_generate_voice': autoGenerateVoice,
        'auto_suggest_visuals': autoSuggestVisuals,
      }),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationOpportunitySearchResponse> searchGenerationOpportunities({
    required String niche,
    required String query,
    String language = 'pt-BR',
    String region = 'BR',
    String timeWindow = 'week',
    int count = 5,
  }) async {
    final response = await _client.post(
      _uri('/generation/opportunities/search'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'niche': niche,
        'query': query,
        'language': language,
        'region': region,
        'time_window': timeWindow,
        'count': count,
      }),
    );
    _throwIfBad(response);
    return GenerationOpportunitySearchResponse.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationProject> createGenerationProjectFromOpportunity({
    required GenerationOpportunity opportunity,
    required int durationSeconds,
    String scriptDepth = 'normal',
    String narrativeStyle = 'documentary',
    bool autoGenerateScript = true,
    bool autoGenerateVoice = false,
    bool autoSuggestVisuals = false,
    String extraContext = '',
  }) async {
    final response = await _client.post(
      _uri('/generation/projects/from-opportunity'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'opportunity': opportunity.toJson(),
        'duration_seconds': durationSeconds,
        'script_depth': scriptDepth,
        'narrative_style': narrativeStyle,
        'auto_generate_script': autoGenerateScript,
        'auto_generate_voice': autoGenerateVoice,
        'auto_suggest_visuals': autoSuggestVisuals,
        'extra_context': extraContext,
      }),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<List<GenerationProject>>
  createGenerationProjectsFromOpportunitiesBatch({
    required List<GenerationOpportunity> opportunities,
    required int durationSeconds,
    String scriptDepth = 'normal',
    String narrativeStyle = 'documentary',
    bool autoGenerateScript = true,
    bool autoGenerateVoice = false,
    bool autoSuggestVisuals = false,
  }) async {
    final response = await _client.post(
      _uri('/generation/projects/from-opportunities-batch'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'opportunities': opportunities.map((item) => item.toJson()).toList(),
        'duration_seconds': durationSeconds,
        'script_depth': scriptDepth,
        'narrative_style': narrativeStyle,
        'auto_generate_script': autoGenerateScript,
        'auto_generate_voice': autoGenerateVoice,
        'auto_suggest_visuals': autoSuggestVisuals,
        'max_projects': opportunities.length,
      }),
    );
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    return (payload['projects'] as List<dynamic>? ?? [])
        .map((item) => GenerationProject.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<GenerationProject> fetchGenerationProject(String projectId) async {
    final response = await _client
        .get(_uri('/generation/projects/$projectId'))
        .timeout(const Duration(seconds: 15));
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

  Future<GenerationProject> suggestGenerationVisuals(String projectId) async {
    final response = await _client.post(
      _uri('/generation/projects/$projectId/visuals/suggest'),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationProject> updateGenerationVisuals({
    required String projectId,
    required List<Map<String, dynamic>> items,
  }) async {
    final response = await _client.put(
      _uri('/generation/projects/$projectId/visuals'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'visual_items': items}),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationProject> addGenerationVisual({
    required String projectId,
    required Map<String, dynamic> item,
  }) async {
    final response = await _client.post(
      _uri('/generation/projects/$projectId/visuals'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(item),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationProject> deleteGenerationVisual({
    required String projectId,
    required String visualId,
  }) async {
    final response = await _client.delete(
      _uri('/generation/projects/$projectId/visuals/$visualId'),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationProject> selectGenerationVisual({
    required String projectId,
    required String visualId,
  }) async {
    final response = await _client.post(
      _uri('/generation/projects/$projectId/visuals/$visualId/select'),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationProject> rejectGenerationVisual({
    required String projectId,
    required String visualId,
  }) async {
    final response = await _client.post(
      _uri('/generation/projects/$projectId/visuals/$visualId/reject'),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationProject> markGenerationVisualsReady(String projectId) async {
    final response = await _client.post(
      _uri('/generation/projects/$projectId/visuals/mark-ready'),
    );
    _throwIfBad(response);
    return GenerationProject.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationStockSearchResponse> searchGenerationStockMedia({
    required String query,
    String orientation = 'portrait',
  }) async {
    final response = await _client.post(
      _uri('/generation/visuals/search-stock'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'query': query, 'orientation': orientation}),
    );
    _throwIfBad(response);
    return GenerationStockSearchResponse.fromJson(
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

  /// Ensure render prerequisites (words.json, downloaded visuals, status)
  /// without rendering. Downloads Pexels b-roll; enables a visible fallback
  /// only when [allowVisualFallback] is set.
  Future<GenerationRenderPrepare> prepareGenerationRender(
    String projectId, {
    bool markVisualReady = false,
    bool allowVisualFallback = false,
  }) async {
    final response = await _client
        .post(
          _uri('/generation/projects/$projectId/render/prepare'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'mark_visual_ready': markVisualReady,
            'allow_visual_fallback': allowVisualFallback,
          }),
        )
        .timeout(const Duration(seconds: 60));
    _throwIfBad(response);
    return GenerationRenderPrepare.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  /// Enqueue a background render job. Returns the created job handle.
  Future<GenerationJob> startGenerationRender(
    String projectId, {
    bool allowVisualFallback = false,
    bool force = false,
  }) async {
    final response = await _client
        .post(
          _uri('/generation/projects/$projectId/render'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'overwrite': true,
            'allow_visual_fallback': allowVisualFallback,
            'force': force,
          }),
        )
        .timeout(const Duration(seconds: 20));
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    return GenerationJob.fromJson(payload['job'] as Map<String, dynamic>);
  }

  /// Poll render status (project render fields + latest job). Short timeout so
  /// a slow backend never hangs the polling UI.
  Future<GenerationRenderStatus> fetchGenerationRenderStatus(
    String projectId,
  ) async {
    final response = await _client
        .get(_uri('/generation/projects/$projectId/render/status'))
        .timeout(const Duration(seconds: 15));
    _throwIfBad(response);
    return GenerationRenderStatus.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationPerformance> fetchGenerationPerformance({bool refresh = false}) async {
    final response = await _client
        .get(_uri('/generation/performance', {if (refresh) 'refresh': 'true'}))
        .timeout(const Duration(seconds: 60));
    _throwIfBad(response);
    return GenerationPerformance.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<void> markGenerationProjectPosted({
    required String projectId,
    required String platform,
    required String url,
    int? views,
    double? retention,
    double? ctr,
    String notes = '',
  }) async {
    final response = await _client.post(
      _uri('/generation/projects/$projectId/posted'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'platform': platform,
        'url': url,
        'views': views,
        'retention': retention,
        'ctr': ctr,
        'notes': notes,
      }),
    );
    _throwIfBad(response);
  }

  Future<List<GenerationPersona>> fetchGenerationPersonas() async {
    final response = await _client
        .get(_uri('/generation/personas'))
        .timeout(const Duration(seconds: 15));
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    return (payload['personas'] as List<dynamic>? ?? [])
        .map((item) => GenerationPersona.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  /// One-shot auto generation: theme (+ studio/persona) -> full video.
  Future<GenerationAutoStart> startAutoGeneration({
    required String theme,
    String persona = '',
    String language = 'pt-BR',
    String speed = 'normal',
    String voice = '',
  }) async {
    final response = await _client
        .post(
          _uri('/generation/auto'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'theme': theme,
            'persona': persona,
            'language': language,
            'speed': speed,
            'voice': voice,
          }),
        )
        .timeout(const Duration(seconds: 20));
    _throwIfBad(response);
    return GenerationAutoStart.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  /// Top trending história/curiosidades topics (YouTube/TikTok) to seed themes.
  Future<List<GenerationTrend>> fetchTrendingTopics({
    String niche = 'história e curiosidades',
    String language = 'pt-BR',
    int limit = 10,
    bool refresh = false,
  }) async {
    final response = await _client
        .get(_uri('/generation/trends', {
          'niche': niche,
          'language': language,
          'limit': '$limit',
          'refresh': refresh ? 'true' : 'false',
        }))
        .timeout(const Duration(seconds: 45));
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    return (payload['topics'] as List<dynamic>? ?? [])
        .map((item) => GenerationTrend.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  /// Publish pack (titles, description, hashtags, best times) in the video's language.
  Future<PublishPack> fetchGenerationPublishPack(String projectId,
      {bool refresh = false}) async {
    final response = await _client
        .get(_uri('/generation/projects/$projectId/publish',
            {'refresh': refresh ? 'true' : 'false'}))
        .timeout(const Duration(seconds: 45));
    _throwIfBad(response);
    return PublishPack.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  /// One theme -> one auto video per language (e.g. pt-BR + en-US for 2 channels).
  Future<List<GenerationAutoStartItem>> startAutoGenerationBatch({
    required String theme,
    String persona = '',
    String speed = 'normal',
    String voice = '',
    List<String> languages = const ['pt-BR', 'en-US'],
  }) async {
    final response = await _client
        .post(
          _uri('/generation/auto/batch'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'theme': theme,
            'persona': persona,
            'speed': speed,
            'voice': voice,
            'languages': languages,
          }),
        )
        .timeout(const Duration(seconds: 30));
    _throwIfBad(response);
    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    return (payload['items'] as List<dynamic>? ?? [])
        .map((item) =>
            GenerationAutoStartItem.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  /// Unified auto-generation status (script -> visuals -> voice -> render).
  Future<GenerationAutoStatus> fetchAutoStatus(String projectId) async {
    final response = await _client
        .get(_uri('/generation/projects/$projectId/auto/status'))
        .timeout(const Duration(seconds: 15));
    _throwIfBad(response);
    return GenerationAutoStatus.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationJob> cancelGenerationJob(String jobId) async {
    final response = await _client
        .post(_uri('/generation/jobs/$jobId/cancel'))
        .timeout(const Duration(seconds: 15));
    _throwIfBad(response);
    return GenerationJob.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<GenerationJob> retryGenerationJob(String jobId) async {
    final response = await _client
        .post(_uri('/generation/jobs/$jobId/retry'))
        .timeout(const Duration(seconds: 15));
    _throwIfBad(response);
    return GenerationJob.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
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

class GenerationPerformance {
  const GenerationPerformance({
    required this.videos,
    required this.totalPosted,
    required this.byStudio,
    required this.byNiche,
  });

  final List<GenerationPerfVideo> videos;
  final int totalPosted;
  final List<GenerationPerfGroup> byStudio;
  final List<GenerationPerfGroup> byNiche;

  factory GenerationPerformance.fromJson(Map<String, dynamic> json) {
    List<T> parse<T>(String key, T Function(Map<String, dynamic>) fn) =>
        (json[key] as List<dynamic>? ?? [])
            .map((e) => fn(e as Map<String, dynamic>))
            .toList();
    return GenerationPerformance(
      videos: parse('videos', GenerationPerfVideo.fromJson),
      totalPosted: _intValue(json['total_posted']),
      byStudio: parse('by_studio', GenerationPerfGroup.fromJson),
      byNiche: parse('by_niche', GenerationPerfGroup.fromJson),
    );
  }
}

class GenerationPerfVideo {
  const GenerationPerfVideo({
    required this.projectId,
    required this.title,
    required this.personaLabel,
    required this.niche,
    required this.platform,
    required this.url,
    required this.views,
    required this.likes,
    required this.retention,
    required this.ctr,
  });

  final String projectId;
  final String title;
  final String personaLabel;
  final String niche;
  final String platform;
  final String url;
  final int views;
  final int likes;
  final double retention;
  final double ctr;

  factory GenerationPerfVideo.fromJson(Map<String, dynamic> json) {
    double d(Object? v) => v is num ? v.toDouble() : double.tryParse(v?.toString() ?? '') ?? 0.0;
    return GenerationPerfVideo(
      projectId: json['project_id']?.toString() ?? '',
      title: json['title']?.toString() ?? '',
      personaLabel: json['persona_label']?.toString() ?? '—',
      niche: json['niche']?.toString() ?? '—',
      platform: json['platform']?.toString() ?? '',
      url: json['url']?.toString() ?? '',
      views: _intValue(json['views']),
      likes: _intValue(json['likes']),
      retention: d(json['retention']),
      ctr: d(json['ctr']),
    );
  }
}

class GenerationPerfGroup {
  const GenerationPerfGroup({
    required this.name,
    required this.count,
    required this.avgViews,
    required this.totalViews,
  });

  final String name;
  final int count;
  final double avgViews;
  final int totalViews;

  factory GenerationPerfGroup.fromJson(Map<String, dynamic> json) {
    return GenerationPerfGroup(
      name: json['name']?.toString() ?? '—',
      count: _intValue(json['count']),
      avgViews: json['avg_views'] is num
          ? (json['avg_views'] as num).toDouble()
          : double.tryParse(json['avg_views']?.toString() ?? '') ?? 0.0,
      totalViews: _intValue(json['total_views']),
    );
  }
}

class GenerationPersona {
  const GenerationPersona({
    required this.id,
    required this.label,
    required this.description,
    required this.icon,
    required this.accent,
    required this.voice,
    required this.niche,
  });

  final String id;
  final String label;
  final String description;
  final String icon;
  final String accent;
  final String voice;
  final String niche;

  factory GenerationPersona.fromJson(Map<String, dynamic> json) {
    return GenerationPersona(
      id: json['id']?.toString() ?? '',
      label: json['label']?.toString() ?? '',
      description: json['description']?.toString() ?? '',
      icon: json['icon']?.toString() ?? '',
      accent: json['accent']?.toString() ?? '',
      voice: json['voice']?.toString() ?? '',
      niche: json['niche']?.toString() ?? '',
    );
  }
}

class GenerationAutoStart {
  const GenerationAutoStart({
    required this.projectId,
    required this.jobId,
    required this.autoStatus,
  });

  final String projectId;
  final String jobId;
  final String autoStatus;

  factory GenerationAutoStart.fromJson(Map<String, dynamic> json) {
    return GenerationAutoStart(
      projectId: json['project_id']?.toString() ?? '',
      jobId: json['job_id']?.toString() ?? '',
      autoStatus: json['auto_status']?.toString() ?? '',
    );
  }
}

/// One language's result inside a batch auto-generation (theme -> N videos).
class GenerationAutoStartItem {
  const GenerationAutoStartItem({
    required this.language,
    required this.projectId,
    required this.jobId,
    required this.error,
  });

  final String language;
  final String projectId;
  final String jobId;
  final String error;

  bool get ok => projectId.isNotEmpty && error.isEmpty;

  factory GenerationAutoStartItem.fromJson(Map<String, dynamic> json) {
    return GenerationAutoStartItem(
      language: json['language']?.toString() ?? '',
      projectId: json['project_id']?.toString() ?? '',
      jobId: json['job_id']?.toString() ?? '',
      error: json['error']?.toString() ?? '',
    );
  }
}

/// Copy-paste publish pack for one video (one language).
class PublishPack {
  const PublishPack({
    required this.titles,
    required this.description,
    required this.hashtags,
    required this.bestTimes,
    required this.language,
  });

  final List<String> titles;
  final String description;
  final List<String> hashtags;
  final String bestTimes;
  final String language;

  factory PublishPack.fromJson(Map<String, dynamic> json) {
    return PublishPack(
      titles: (json['titles'] as List<dynamic>? ?? [])
          .map((e) => e.toString())
          .toList(),
      description: json['description']?.toString() ?? '',
      hashtags: (json['hashtags'] as List<dynamic>? ?? [])
          .map((e) => e.toString())
          .toList(),
      bestTimes: json['best_times']?.toString() ?? '',
      language: json['language']?.toString() ?? '',
    );
  }
}

/// A suggested trending topic to seed the theme field.
class GenerationTrend {
  const GenerationTrend({
    required this.title,
    required this.hook,
    required this.why,
  });

  final String title;
  final String hook;
  final String why;

  factory GenerationTrend.fromJson(Map<String, dynamic> json) {
    return GenerationTrend(
      title: json['title']?.toString() ?? '',
      hook: json['hook']?.toString() ?? '',
      why: json['why']?.toString() ?? '',
    );
  }
}

class GenerationAutoStatus {
  const GenerationAutoStatus({
    required this.projectId,
    required this.status,
    required this.progress,
    required this.title,
    required this.degraded,
    required this.warning,
    required this.videoUrl,
    required this.error,
    required this.scriptQualityScore,
    required this.scriptQualityTier,
  });

  final String projectId;
  final String status; // queued|scripting|visuals|voice|rendering|ready|failed|cancelled
  final double progress;
  final String title;
  final bool degraded;
  final String warning;
  final String videoUrl;
  final String error;
  final double? scriptQualityScore;
  final String scriptQualityTier;

  bool get isTerminal =>
      status == 'ready' || status == 'failed' || status == 'cancelled';

  factory GenerationAutoStatus.fromJson(Map<String, dynamic> json) {
    final score = json['script_quality_score'];
    return GenerationAutoStatus(
      projectId: json['project_id']?.toString() ?? '',
      status: json['status']?.toString() ?? 'queued',
      progress: json['progress'] is num
          ? (json['progress'] as num).toDouble()
          : double.tryParse(json['progress']?.toString() ?? '') ?? 0.0,
      title: json['title']?.toString() ?? '',
      degraded: json['degraded'] == true,
      warning: json['warning']?.toString() ?? '',
      videoUrl: json['video_url']?.toString() ?? '',
      error: json['error']?.toString() ?? '',
      scriptQualityScore: score is num
          ? score.toDouble()
          : double.tryParse(score?.toString() ?? ''),
      scriptQualityTier: json['script_quality_tier']?.toString() ?? '',
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

/// Wraps an http.Client to attach the shared API token header on every request,
/// so a publicly-exposed backend (tunnel/cloud) rejects unauthorized callers.
/// No-op when AppConfig.apiToken is empty (local dev).
class _AuthClient extends http.BaseClient {
  _AuthClient(this._inner);

  final http.Client _inner;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) {
    if (AppConfig.apiToken.isNotEmpty) {
      request.headers['X-API-Token'] = AppConfig.apiToken;
    }
    return _inner.send(request);
  }

  @override
  void close() => _inner.close();
}
