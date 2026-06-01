import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/review_clip.dart';
import '../models/review_summary.dart';
import '../models/final_clip.dart';
import '../models/final_summary.dart';
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

  void _throwIfBad(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) return;
    throw ApiException('HTTP ${response.statusCode}: ${response.body}');
  }
}

class ApiException implements Exception {
  ApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
