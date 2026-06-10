class GenerationIdea {
  const GenerationIdea({
    required this.ideaId,
    required this.title,
    required this.angle,
    required this.hook,
    required this.whyItMightWork,
    required this.targetEmotion,
    required this.curiosityGap,
    required this.riskLevel,
    required this.factCheckNeeded,
    required this.suggestedHashtags,
    required this.visualDirection,
    required this.engineMode,
    required this.provider,
    required this.fallbackUsed,
    required this.niche,
    required this.topic,
    required this.language,
    required this.tone,
  });

  final String ideaId;
  final String title;
  final String angle;
  final String hook;
  final String whyItMightWork;
  final String targetEmotion;
  final String curiosityGap;
  final String riskLevel;
  final bool factCheckNeeded;
  final List<String> suggestedHashtags;
  final String visualDirection;
  final String engineMode;
  final String provider;
  final bool fallbackUsed;
  final String niche;
  final String topic;
  final String language;
  final String tone;

  factory GenerationIdea.fromJson(Map<String, dynamic> json) {
    return GenerationIdea(
      ideaId: _string(json['idea_id']),
      title: _string(json['title']),
      angle: _string(json['angle']),
      hook: _string(json['hook']),
      whyItMightWork: _string(json['why_it_might_work']),
      targetEmotion: _string(json['target_emotion']),
      curiosityGap: _string(json['curiosity_gap']),
      riskLevel: _string(json['risk_level']),
      factCheckNeeded: _bool(json['fact_check_needed']),
      suggestedHashtags: _stringList(json['suggested_hashtags']),
      visualDirection: _string(json['visual_direction']),
      engineMode: _string(json['engine_mode']).isEmpty
          ? 'local'
          : _string(json['engine_mode']),
      provider: _string(json['provider']).isEmpty
          ? 'none'
          : _string(json['provider']),
      fallbackUsed: _bool(json['fallback_used']),
      niche: _string(json['niche']),
      topic: _string(json['topic']),
      language: _string(json['language']),
      tone: _string(json['tone']),
    );
  }
}

class GenerationScript {
  const GenerationScript({
    required this.title,
    required this.hook,
    required this.scriptLines,
    required this.cta,
    required this.hashtags,
    required this.visualContext,
    required this.factCheckNotes,
    required this.factualBrief,
    required this.factualGroundingUsed,
    required this.factualGroundingConfidence,
    required this.specificityScore,
    required this.estimatedDurationSeconds,
    required this.voiceStyle,
    required this.pacing,
    required this.engineMode,
    required this.provider,
    required this.fallbackUsed,
    required this.scriptQualityScore,
    required this.scriptQualityTier,
    required this.scriptPositiveSignals,
    required this.scriptNegativeSignals,
    required this.scriptRejectReason,
    required this.niche,
    required this.language,
    required this.tone,
    required this.status,
  });

  final String title;
  final String hook;
  final List<String> scriptLines;
  final String cta;
  final List<String> hashtags;
  final List<String> visualContext;
  final List<String> factCheckNotes;
  final Map<String, dynamic> factualBrief;
  final bool factualGroundingUsed;
  final String factualGroundingConfidence;
  final num? specificityScore;
  final num? estimatedDurationSeconds;
  final String voiceStyle;
  final String pacing;
  final String engineMode;
  final String provider;
  final bool fallbackUsed;
  final num? scriptQualityScore;
  final String scriptQualityTier;
  final List<String> scriptPositiveSignals;
  final List<String> scriptNegativeSignals;
  final String scriptRejectReason;
  final String niche;
  final String language;
  final String tone;
  final String status;

  factory GenerationScript.fromJson(Map<String, dynamic> json) {
    return GenerationScript(
      title: _string(json['title']),
      hook: _string(json['hook']),
      scriptLines: _stringList(json['script_lines']),
      cta: _string(json['cta']),
      hashtags: _stringList(json['hashtags']),
      visualContext: _stringList(json['visual_context']),
      factCheckNotes: _stringList(json['fact_check_notes']),
      factualBrief: _map(json['factual_brief']),
      factualGroundingUsed: _bool(json['factual_grounding_used']),
      factualGroundingConfidence: _string(json['factual_grounding_confidence']),
      specificityScore: _num(json['specificity_score']),
      estimatedDurationSeconds: _num(
        json['estimated_duration_seconds'] ?? json['duration_seconds'],
      ),
      voiceStyle: _string(json['voice_style']),
      pacing: _string(json['pacing']),
      engineMode: _string(json['engine_mode']).isEmpty
          ? 'local'
          : _string(json['engine_mode']),
      provider: _string(json['provider']).isEmpty
          ? 'none'
          : _string(json['provider']),
      fallbackUsed: _bool(json['fallback_used']),
      scriptQualityScore: _num(json['script_quality_score']),
      scriptQualityTier: _string(json['script_quality_tier']),
      scriptPositiveSignals: _stringList(json['script_positive_signals']),
      scriptNegativeSignals: _stringList(json['script_negative_signals']),
      scriptRejectReason: _string(json['script_reject_reason']),
      niche: _string(json['niche']),
      language: _string(json['language']),
      tone: _string(json['tone']),
      status: _string(json['status']),
    );
  }

  Map<String, dynamic> toProjectJson({String idea = ''}) {
    return {
      'title': title,
      'niche': niche,
      'language': language,
      'tone': tone,
      'status': 'script',
      'idea': idea,
      'hook': hook,
      'script_lines': scriptLines,
      'cta': cta,
      'hashtags': hashtags,
      'visual_context': visualContext,
      'fact_check_notes': factCheckNotes,
      'factual_brief': factualBrief,
      'factual_grounding_used': factualGroundingUsed,
      'factual_grounding_confidence': factualGroundingConfidence,
      'specificity_score': specificityScore,
      'estimated_duration_seconds': estimatedDurationSeconds,
      'voice_style': voiceStyle,
      'pacing': pacing,
      'engine_mode': engineMode,
      'provider': provider,
      'fallback_used': fallbackUsed,
      'script_quality_score': scriptQualityScore,
      'script_quality_tier': scriptQualityTier,
      'script_positive_signals': scriptPositiveSignals,
      'script_negative_signals': scriptNegativeSignals,
      'script_reject_reason': scriptRejectReason,
    };
  }
}

class GenerationProject {
  const GenerationProject({
    required this.projectId,
    required this.title,
    required this.niche,
    required this.language,
    required this.tone,
    required this.status,
    required this.idea,
    required this.hook,
    required this.scriptLines,
    required this.cta,
    required this.hashtags,
    required this.visualContext,
    required this.engineMode,
    required this.provider,
    required this.fallbackUsed,
    required this.factCheckNotes,
    required this.factualBrief,
    required this.factualGroundingUsed,
    required this.factualGroundingConfidence,
    required this.specificityScore,
    required this.estimatedDurationSeconds,
    required this.voiceStyle,
    required this.pacing,
    required this.scriptQualityScore,
    required this.scriptQualityTier,
    required this.scriptPositiveSignals,
    required this.scriptNegativeSignals,
    required this.scriptRejectReason,
    required this.guardrailStatus,
    required this.guardrailRisks,
    required this.disclosureRecommended,
    required this.factCheckRequired,
    required this.copyrightReviewRequired,
    required this.platformNotes,
    required this.voiceStatus,
    required this.voiceName,
    required this.voiceProvider,
    required this.voiceRate,
    required this.voicePitch,
    required this.voiceAudioPath,
    required this.voiceAudioUrl,
    required this.voiceDurationSeconds,
    required this.voiceGeneratedAt,
    required this.voiceError,
    required this.createdAt,
    required this.updatedAt,
  });

  final String projectId;
  final String title;
  final String niche;
  final String language;
  final String tone;
  final String status;
  final String idea;
  final String hook;
  final List<String> scriptLines;
  final String cta;
  final List<String> hashtags;
  final List<String> visualContext;
  final String engineMode;
  final String provider;
  final bool fallbackUsed;
  final List<String> factCheckNotes;
  final Map<String, dynamic> factualBrief;
  final bool factualGroundingUsed;
  final String factualGroundingConfidence;
  final num? specificityScore;
  final num? estimatedDurationSeconds;
  final String voiceStyle;
  final String pacing;
  final num? scriptQualityScore;
  final String scriptQualityTier;
  final List<String> scriptPositiveSignals;
  final List<String> scriptNegativeSignals;
  final String scriptRejectReason;
  final String guardrailStatus;
  final List<String> guardrailRisks;
  final bool disclosureRecommended;
  final bool factCheckRequired;
  final bool copyrightReviewRequired;
  final List<String> platformNotes;
  final String voiceStatus;
  final String voiceName;
  final String voiceProvider;
  final String voiceRate;
  final String voicePitch;
  final String voiceAudioPath;
  final String voiceAudioUrl;
  final num? voiceDurationSeconds;
  final String voiceGeneratedAt;
  final String voiceError;
  final String createdAt;
  final String updatedAt;

  factory GenerationProject.fromJson(Map<String, dynamic> json) {
    return GenerationProject(
      projectId: _string(json['project_id']),
      title: _string(json['title']),
      niche: _string(json['niche']),
      language: _string(json['language']),
      tone: _string(json['tone']),
      status: _string(json['status']),
      idea: _string(json['idea']),
      hook: _string(json['hook']),
      scriptLines: _stringList(json['script_lines']),
      cta: _string(json['cta']),
      hashtags: _stringList(json['hashtags']),
      visualContext: _stringList(json['visual_context']),
      engineMode: _string(json['engine_mode']).isEmpty
          ? 'local'
          : _string(json['engine_mode']),
      provider: _string(json['provider']).isEmpty
          ? 'none'
          : _string(json['provider']),
      fallbackUsed: _bool(json['fallback_used']),
      factCheckNotes: _stringList(json['fact_check_notes']),
      factualBrief: _map(json['factual_brief']),
      factualGroundingUsed: _bool(json['factual_grounding_used']),
      factualGroundingConfidence: _string(json['factual_grounding_confidence']),
      specificityScore: _num(json['specificity_score']),
      estimatedDurationSeconds: _num(json['estimated_duration_seconds']),
      voiceStyle: _string(json['voice_style']),
      pacing: _string(json['pacing']),
      scriptQualityScore: _num(json['script_quality_score']),
      scriptQualityTier: _string(json['script_quality_tier']),
      scriptPositiveSignals: _stringList(json['script_positive_signals']),
      scriptNegativeSignals: _stringList(json['script_negative_signals']),
      scriptRejectReason: _string(json['script_reject_reason']),
      guardrailStatus: _string(json['guardrail_status']),
      guardrailRisks: _stringList(json['guardrail_risks']),
      disclosureRecommended: _bool(json['disclosure_recommended']),
      factCheckRequired: _bool(json['fact_check_required']),
      copyrightReviewRequired: _bool(json['copyright_review_required']),
      platformNotes: _stringList(json['platform_notes']),
      voiceStatus: _string(json['voice_status']).isEmpty
          ? 'none'
          : _string(json['voice_status']),
      voiceName: _string(json['voice_name']),
      voiceProvider: _string(json['voice_provider']),
      voiceRate: _string(json['voice_rate']),
      voicePitch: _string(json['voice_pitch']),
      voiceAudioPath: _string(json['voice_audio_path']),
      voiceAudioUrl: _string(json['voice_audio_url']),
      voiceDurationSeconds: _num(json['voice_duration_seconds']),
      voiceGeneratedAt: _string(json['voice_generated_at']),
      voiceError: _string(json['voice_error']),
      createdAt: _string(json['created_at']),
      updatedAt: _string(json['updated_at']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'niche': niche,
      'language': language,
      'tone': tone,
      'status': status,
      'idea': idea,
      'hook': hook,
      'script_lines': scriptLines,
      'cta': cta,
      'hashtags': hashtags,
      'visual_context': visualContext,
      'engine_mode': engineMode,
      'provider': provider,
      'fallback_used': fallbackUsed,
      'fact_check_notes': factCheckNotes,
      'factual_brief': factualBrief,
      'factual_grounding_used': factualGroundingUsed,
      'factual_grounding_confidence': factualGroundingConfidence,
      'specificity_score': specificityScore,
      'estimated_duration_seconds': estimatedDurationSeconds,
      'voice_style': voiceStyle,
      'pacing': pacing,
      'script_quality_score': scriptQualityScore,
      'script_quality_tier': scriptQualityTier,
      'script_positive_signals': scriptPositiveSignals,
      'script_negative_signals': scriptNegativeSignals,
      'script_reject_reason': scriptRejectReason,
      'guardrail_status': guardrailStatus,
      'guardrail_risks': guardrailRisks,
      'disclosure_recommended': disclosureRecommended,
      'fact_check_required': factCheckRequired,
      'copyright_review_required': copyrightReviewRequired,
      'platform_notes': platformNotes,
      'voice_status': voiceStatus,
      'voice_name': voiceName,
      'voice_provider': voiceProvider,
      'voice_rate': voiceRate,
      'voice_pitch': voicePitch,
      'voice_audio_path': voiceAudioPath,
      'voice_audio_url': voiceAudioUrl,
      'voice_duration_seconds': voiceDurationSeconds,
      'voice_generated_at': voiceGeneratedAt,
      'voice_error': voiceError,
    };
  }
}

class GenerationEngineStatus {
  const GenerationEngineStatus({
    required this.engineMode,
    required this.provider,
    required this.externalAiAvailable,
    required this.fallbackAvailable,
    required this.requireExternalAi,
    required this.geminiConfigured,
    required this.geminiModel,
    required this.features,
  });

  final String engineMode;
  final String provider;
  final bool externalAiAvailable;
  final bool fallbackAvailable;
  final bool requireExternalAi;
  final bool geminiConfigured;
  final String geminiModel;
  final List<String> features;

  factory GenerationEngineStatus.fromJson(Map<String, dynamic> json) {
    return GenerationEngineStatus(
      engineMode: _string(json['engine_mode']).isEmpty
          ? 'local'
          : _string(json['engine_mode']),
      provider: _string(json['provider']).isEmpty
          ? 'none'
          : _string(json['provider']),
      externalAiAvailable: _bool(json['external_ai_available']),
      fallbackAvailable: _bool(json['fallback_available']),
      requireExternalAi: _bool(json['require_external_ai']),
      geminiConfigured: _bool(json['gemini_configured']),
      geminiModel: _string(json['gemini_model']),
      features: _stringList(json['features']),
    );
  }
}

class GenerationVoice {
  const GenerationVoice({
    required this.name,
    required this.label,
    required this.locale,
    required this.gender,
    required this.provider,
  });

  final String name;
  final String label;
  final String locale;
  final String gender;
  final String provider;

  factory GenerationVoice.fromJson(Map<String, dynamic> json) {
    return GenerationVoice(
      name: _string(json['name']),
      label: _string(json['label']),
      locale: _string(json['locale']),
      gender: _string(json['gender']),
      provider: _string(json['provider']),
    );
  }
}

class GenerationVoicesResponse {
  const GenerationVoicesResponse({
    required this.available,
    required this.installHint,
    required this.voices,
  });

  final bool available;
  final String installHint;
  final List<GenerationVoice> voices;

  factory GenerationVoicesResponse.fromJson(Map<String, dynamic> json) {
    return GenerationVoicesResponse(
      available: json['available'] == true,
      installHint: _string(json['install_hint']),
      voices: _mapList(json['voices']).map(GenerationVoice.fromJson).toList(),
    );
  }
}

String _string(Object? value) => value?.toString() ?? '';

bool _bool(Object? value) {
  if (value is bool) return value;
  final text = value?.toString().toLowerCase().trim() ?? '';
  return text == 'true' || text == '1' || text == 'yes' || text == 'sim';
}

num? _num(Object? value) {
  if (value is num) return value;
  return num.tryParse(value?.toString() ?? '');
}

List<String> _stringList(Object? value) {
  if (value is Map) {
    return value.entries
        .map((entry) => '${entry.key}: ${entry.value}')
        .where((item) => item.trim().isNotEmpty)
        .toList();
  }
  if (value is! List) return const [];
  return value
      .map((item) => item.toString())
      .where((item) => item.isNotEmpty)
      .toList();
}

Map<String, dynamic> _map(Object? value) {
  if (value is! Map) return const {};
  return value.map((key, item) => MapEntry(key.toString(), item));
}

List<Map<String, dynamic>> _mapList(Object? value) {
  if (value is! List) return const [];
  return value.whereType<Map>().map((item) {
    return item.map((key, value) => MapEntry(key.toString(), value));
  }).toList();
}
