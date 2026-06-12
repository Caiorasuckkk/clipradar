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
    required this.researchBrief,
    required this.researchCacheHit,
    required this.sourceUrls,
    required this.sourceTitles,
    required this.groundingUsed,
    required this.groundingAvailable,
    required this.searchQueries,
    required this.factualGroundingUsed,
    required this.factualGroundingConfidence,
    required this.specificityScore,
    required this.scriptDepth,
    required this.scriptDepthLabel,
    required this.narrativeStyle,
    required this.narrativeStyleLabel,
    required this.narrativePlan,
    required this.storyBeats,
    required this.claimEvidencePairs,
    required this.depthScore,
    required this.narrativeScore,
    required this.retentionScore,
    required this.shallowScriptDetected,
    required this.narrativeRepairApplied,
    required this.narrativeRepairReason,
    required this.requestedDurationSeconds,
    required this.durationPresetLabel,
    required this.scriptWordCount,
    required this.narrationWordCount,
    required this.narrationTextPreview,
    required this.forceResearchUsed,
    required this.llmCallCount,
    required this.researchCallCount,
    required this.scriptCallCount,
    required this.lastLlmError,
    required this.lastLlmProvider,
    required this.lastLlmModel,
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
    required this.contentFormat,
    required this.contentFormatLabel,
    required this.concretePromise,
    required this.viewerReasonToWatch,
    required this.watchabilityScore,
    required this.needsMoreContext,
    required this.missingContextFields,
    required this.watchabilityPositiveSignals,
    required this.watchabilityNegativeSignals,
  });

  final String title;
  final String hook;
  final List<String> scriptLines;
  final String cta;
  final List<String> hashtags;
  final List<String> visualContext;
  final List<String> factCheckNotes;
  final Map<String, dynamic> factualBrief;
  final Map<String, dynamic> researchBrief;
  final bool researchCacheHit;
  final List<String> sourceUrls;
  final List<String> sourceTitles;
  final bool groundingUsed;
  final bool groundingAvailable;
  final List<String> searchQueries;
  final bool factualGroundingUsed;
  final String factualGroundingConfidence;
  final num? specificityScore;
  final String scriptDepth;
  final String scriptDepthLabel;
  final String narrativeStyle;
  final String narrativeStyleLabel;
  final Map<String, dynamic> narrativePlan;
  final List<Map<String, dynamic>> storyBeats;
  final List<Map<String, dynamic>> claimEvidencePairs;
  final num? depthScore;
  final num? narrativeScore;
  final num? retentionScore;
  final bool shallowScriptDetected;
  final bool narrativeRepairApplied;
  final String narrativeRepairReason;
  final num? requestedDurationSeconds;
  final String durationPresetLabel;
  final int scriptWordCount;
  final int narrationWordCount;
  final String narrationTextPreview;
  final bool forceResearchUsed;
  final int llmCallCount;
  final int researchCallCount;
  final int scriptCallCount;
  final String lastLlmError;
  final String lastLlmProvider;
  final String lastLlmModel;
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
  final String contentFormat;
  final String contentFormatLabel;
  final String concretePromise;
  final String viewerReasonToWatch;
  final num? watchabilityScore;
  final bool needsMoreContext;
  final List<String> missingContextFields;
  final List<String> watchabilityPositiveSignals;
  final List<String> watchabilityNegativeSignals;

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
      researchBrief: _map(json['research_brief']),
      researchCacheHit: _bool(json['research_cache_hit']),
      sourceUrls: _stringList(json['source_urls']),
      sourceTitles: _stringList(json['source_titles']),
      groundingUsed: _bool(json['grounding_used']),
      groundingAvailable: _bool(json['grounding_available']),
      searchQueries: _stringList(json['search_queries']),
      factualGroundingUsed: _bool(json['factual_grounding_used']),
      factualGroundingConfidence: _string(json['factual_grounding_confidence']),
      specificityScore: _num(json['specificity_score']),
      scriptDepth: _string(json['script_depth']).isEmpty
          ? 'normal'
          : _string(json['script_depth']),
      scriptDepthLabel: _string(json['script_depth_label']).isEmpty
          ? 'Normal'
          : _string(json['script_depth_label']),
      narrativeStyle: _string(json['narrative_style']).isEmpty
          ? 'dramatic'
          : _string(json['narrative_style']),
      narrativeStyleLabel: _string(json['narrative_style_label']).isEmpty
          ? 'Dramático'
          : _string(json['narrative_style_label']),
      narrativePlan: _map(json['narrative_plan']),
      storyBeats: _mapList(json['story_beats']),
      claimEvidencePairs: _mapList(json['claim_evidence_pairs']),
      depthScore: _num(json['depth_score']),
      narrativeScore: _num(json['narrative_score']),
      retentionScore: _num(json['retention_score']),
      shallowScriptDetected: _bool(json['shallow_script_detected']),
      narrativeRepairApplied: _bool(json['narrative_repair_applied']),
      narrativeRepairReason: _string(json['narrative_repair_reason']),
      requestedDurationSeconds: _num(json['requested_duration_seconds']),
      durationPresetLabel: _string(json['duration_preset_label']),
      scriptWordCount: _int(json['script_word_count']),
      narrationWordCount: _int(json['narration_word_count']),
      narrationTextPreview: _string(json['narration_text_preview']),
      forceResearchUsed: _bool(json['force_research_used']),
      llmCallCount: _int(json['llm_call_count']),
      researchCallCount: _int(json['research_call_count']),
      scriptCallCount: _int(json['script_call_count']),
      lastLlmError: _string(json['last_llm_error']),
      lastLlmProvider: _string(json['last_llm_provider']),
      lastLlmModel: _string(json['last_llm_model']),
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
      contentFormat: _string(json['content_format']).isEmpty
          ? 'manual_topic'
          : _string(json['content_format']),
      contentFormatLabel: _string(json['content_format_label']).isEmpty
          ? 'Tema manual'
          : _string(json['content_format_label']),
      concretePromise: _string(json['concrete_promise']),
      viewerReasonToWatch: _string(json['viewer_reason_to_watch']),
      watchabilityScore: _num(json['watchability_score']),
      needsMoreContext: _bool(json['needs_more_context']),
      missingContextFields: _stringList(json['missing_context_fields']),
      watchabilityPositiveSignals: _stringList(
        json['watchability_positive_signals'],
      ),
      watchabilityNegativeSignals: _stringList(
        json['watchability_negative_signals'],
      ),
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
      'research_brief': researchBrief,
      'research_cache_hit': researchCacheHit,
      'source_urls': sourceUrls,
      'source_titles': sourceTitles,
      'grounding_used': groundingUsed,
      'grounding_available': groundingAvailable,
      'search_queries': searchQueries,
      'factual_grounding_used': factualGroundingUsed,
      'factual_grounding_confidence': factualGroundingConfidence,
      'specificity_score': specificityScore,
      'script_depth': scriptDepth,
      'script_depth_label': scriptDepthLabel,
      'narrative_style': narrativeStyle,
      'narrative_style_label': narrativeStyleLabel,
      'narrative_plan': narrativePlan,
      'story_beats': storyBeats,
      'claim_evidence_pairs': claimEvidencePairs,
      'depth_score': depthScore,
      'narrative_score': narrativeScore,
      'retention_score': retentionScore,
      'shallow_script_detected': shallowScriptDetected,
      'narrative_repair_applied': narrativeRepairApplied,
      'narrative_repair_reason': narrativeRepairReason,
      'requested_duration_seconds': requestedDurationSeconds,
      'duration_preset_label': durationPresetLabel,
      'script_word_count': scriptWordCount,
      'narration_word_count': narrationWordCount,
      'narration_text_preview': narrationTextPreview,
      'force_research_used': forceResearchUsed,
      'llm_call_count': llmCallCount,
      'research_call_count': researchCallCount,
      'script_call_count': scriptCallCount,
      'last_llm_error': lastLlmError,
      'last_llm_provider': lastLlmProvider,
      'last_llm_model': lastLlmModel,
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
      'content_format': contentFormat,
      'content_format_label': contentFormatLabel,
      'concrete_promise': concretePromise,
      'viewer_reason_to_watch': viewerReasonToWatch,
      'watchability_score': watchabilityScore,
      'needs_more_context': needsMoreContext,
      'missing_context_fields': missingContextFields,
      'watchability_positive_signals': watchabilityPositiveSignals,
      'watchability_negative_signals': watchabilityNegativeSignals,
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
    required this.researchBrief,
    required this.researchCacheHit,
    required this.sourceUrls,
    required this.sourceTitles,
    required this.groundingUsed,
    required this.groundingAvailable,
    required this.searchQueries,
    required this.factualGroundingUsed,
    required this.factualGroundingConfidence,
    required this.specificityScore,
    required this.scriptDepth,
    required this.scriptDepthLabel,
    required this.narrativeStyle,
    required this.narrativeStyleLabel,
    required this.narrativePlan,
    required this.storyBeats,
    required this.claimEvidencePairs,
    required this.depthScore,
    required this.narrativeScore,
    required this.retentionScore,
    required this.shallowScriptDetected,
    required this.narrativeRepairApplied,
    required this.narrativeRepairReason,
    required this.requestedDurationSeconds,
    required this.durationPresetLabel,
    required this.scriptWordCount,
    required this.narrationWordCount,
    required this.narrationTextPreview,
    required this.forceResearchUsed,
    required this.llmCallCount,
    required this.researchCallCount,
    required this.scriptCallCount,
    required this.lastLlmError,
    required this.lastLlmProvider,
    required this.lastLlmModel,
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
    required this.visualStatus,
    required this.visualItems,
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
    required this.voiceOutdated,
    required this.creationMode,
    required this.creationModeLabel,
    required this.inputTopic,
    required this.inputIdea,
    required this.inputScript,
    required this.inputNiche,
    required this.inputLanguage,
    required this.inputTone,
    required this.inputCreatedAt,
    required this.opportunityData,
    required this.scriptImportStatus,
    required this.creationWarnings,
    required this.contentFormat,
    required this.contentFormatLabel,
    required this.concretePromise,
    required this.viewerReasonToWatch,
    required this.watchabilityScore,
    required this.needsMoreContext,
    required this.missingContextFields,
    required this.opportunityScriptRepairApplied,
    required this.opportunityScriptRepairReason,
    required this.extraContext,
    required this.watchabilityPositiveSignals,
    required this.watchabilityNegativeSignals,
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
  final Map<String, dynamic> researchBrief;
  final bool researchCacheHit;
  final List<String> sourceUrls;
  final List<String> sourceTitles;
  final bool groundingUsed;
  final bool groundingAvailable;
  final List<String> searchQueries;
  final bool factualGroundingUsed;
  final String factualGroundingConfidence;
  final num? specificityScore;
  final String scriptDepth;
  final String scriptDepthLabel;
  final String narrativeStyle;
  final String narrativeStyleLabel;
  final Map<String, dynamic> narrativePlan;
  final List<Map<String, dynamic>> storyBeats;
  final List<Map<String, dynamic>> claimEvidencePairs;
  final num? depthScore;
  final num? narrativeScore;
  final num? retentionScore;
  final bool shallowScriptDetected;
  final bool narrativeRepairApplied;
  final String narrativeRepairReason;
  final num? requestedDurationSeconds;
  final String durationPresetLabel;
  final int scriptWordCount;
  final int narrationWordCount;
  final String narrationTextPreview;
  final bool forceResearchUsed;
  final int llmCallCount;
  final int researchCallCount;
  final int scriptCallCount;
  final String lastLlmError;
  final String lastLlmProvider;
  final String lastLlmModel;
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
  final String visualStatus;
  final List<GenerationVisualItem> visualItems;
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
  final bool voiceOutdated;
  final String creationMode;
  final String creationModeLabel;
  final String inputTopic;
  final String inputIdea;
  final String inputScript;
  final String inputNiche;
  final String inputLanguage;
  final String inputTone;
  final String inputCreatedAt;
  final Map<String, dynamic> opportunityData;
  final String scriptImportStatus;
  final List<String> creationWarnings;
  final String contentFormat;
  final String contentFormatLabel;
  final String concretePromise;
  final String viewerReasonToWatch;
  final num? watchabilityScore;
  final bool needsMoreContext;
  final List<String> missingContextFields;
  final bool opportunityScriptRepairApplied;
  final String opportunityScriptRepairReason;
  final String extraContext;
  final List<String> watchabilityPositiveSignals;
  final List<String> watchabilityNegativeSignals;
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
      researchBrief: _map(json['research_brief']),
      researchCacheHit: _bool(json['research_cache_hit']),
      sourceUrls: _stringList(json['source_urls']),
      sourceTitles: _stringList(json['source_titles']),
      groundingUsed: _bool(json['grounding_used']),
      groundingAvailable: _bool(json['grounding_available']),
      searchQueries: _stringList(json['search_queries']),
      factualGroundingUsed: _bool(json['factual_grounding_used']),
      factualGroundingConfidence: _string(json['factual_grounding_confidence']),
      specificityScore: _num(json['specificity_score']),
      scriptDepth: _string(json['script_depth']).isEmpty
          ? 'normal'
          : _string(json['script_depth']),
      scriptDepthLabel: _string(json['script_depth_label']).isEmpty
          ? 'Normal'
          : _string(json['script_depth_label']),
      narrativeStyle: _string(json['narrative_style']).isEmpty
          ? 'dramatic'
          : _string(json['narrative_style']),
      narrativeStyleLabel: _string(json['narrative_style_label']).isEmpty
          ? 'Dramático'
          : _string(json['narrative_style_label']),
      narrativePlan: _map(json['narrative_plan']),
      storyBeats: _mapList(json['story_beats']),
      claimEvidencePairs: _mapList(json['claim_evidence_pairs']),
      depthScore: _num(json['depth_score']),
      narrativeScore: _num(json['narrative_score']),
      retentionScore: _num(json['retention_score']),
      shallowScriptDetected: _bool(json['shallow_script_detected']),
      narrativeRepairApplied: _bool(json['narrative_repair_applied']),
      narrativeRepairReason: _string(json['narrative_repair_reason']),
      requestedDurationSeconds: _num(json['requested_duration_seconds']),
      durationPresetLabel: _string(json['duration_preset_label']),
      scriptWordCount: _int(json['script_word_count']),
      narrationWordCount: _int(json['narration_word_count']),
      narrationTextPreview: _string(json['narration_text_preview']),
      forceResearchUsed: _bool(json['force_research_used']),
      llmCallCount: _int(json['llm_call_count']),
      researchCallCount: _int(json['research_call_count']),
      scriptCallCount: _int(json['script_call_count']),
      lastLlmError: _string(json['last_llm_error']),
      lastLlmProvider: _string(json['last_llm_provider']),
      lastLlmModel: _string(json['last_llm_model']),
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
      visualStatus: _string(json['visual_status']).isEmpty
          ? 'none'
          : _string(json['visual_status']),
      visualItems: _mapList(
        json['visual_items'],
      ).map(GenerationVisualItem.fromJson).toList(),
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
      voiceOutdated: _bool(json['voice_outdated']),
      creationMode: _string(json['creation_mode']).isEmpty
          ? 'legacy'
          : _string(json['creation_mode']),
      creationModeLabel: _string(json['creation_mode_label']).isEmpty
          ? 'Legado'
          : _string(json['creation_mode_label']),
      inputTopic: _string(json['input_topic']),
      inputIdea: _string(json['input_idea']),
      inputScript: _string(json['input_script']),
      inputNiche: _string(json['input_niche']),
      inputLanguage: _string(json['input_language']).isEmpty
          ? 'pt-BR'
          : _string(json['input_language']),
      inputTone: _string(json['input_tone']).isEmpty
          ? 'curioso'
          : _string(json['input_tone']),
      inputCreatedAt: _string(json['input_created_at']),
      opportunityData: _map(json['opportunity_data']),
      scriptImportStatus: _string(json['script_import_status']).isEmpty
          ? 'none'
          : _string(json['script_import_status']),
      creationWarnings: _stringList(json['creation_warnings']),
      contentFormat: _string(json['content_format']).isEmpty
          ? 'manual_topic'
          : _string(json['content_format']),
      contentFormatLabel: _string(json['content_format_label']).isEmpty
          ? 'Tema manual'
          : _string(json['content_format_label']),
      concretePromise: _string(json['concrete_promise']),
      viewerReasonToWatch: _string(json['viewer_reason_to_watch']),
      watchabilityScore: _num(json['watchability_score']),
      needsMoreContext: _bool(json['needs_more_context']),
      missingContextFields: _stringList(json['missing_context_fields']),
      opportunityScriptRepairApplied: _bool(
        json['opportunity_script_repair_applied'],
      ),
      opportunityScriptRepairReason: _string(
        json['opportunity_script_repair_reason'],
      ),
      extraContext: _string(json['extra_context']),
      watchabilityPositiveSignals: _stringList(
        json['watchability_positive_signals'],
      ),
      watchabilityNegativeSignals: _stringList(
        json['watchability_negative_signals'],
      ),
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
      'research_brief': researchBrief,
      'research_cache_hit': researchCacheHit,
      'source_urls': sourceUrls,
      'source_titles': sourceTitles,
      'grounding_used': groundingUsed,
      'grounding_available': groundingAvailable,
      'search_queries': searchQueries,
      'factual_grounding_used': factualGroundingUsed,
      'factual_grounding_confidence': factualGroundingConfidence,
      'specificity_score': specificityScore,
      'script_depth': scriptDepth,
      'script_depth_label': scriptDepthLabel,
      'narrative_style': narrativeStyle,
      'narrative_style_label': narrativeStyleLabel,
      'narrative_plan': narrativePlan,
      'story_beats': storyBeats,
      'claim_evidence_pairs': claimEvidencePairs,
      'depth_score': depthScore,
      'narrative_score': narrativeScore,
      'retention_score': retentionScore,
      'shallow_script_detected': shallowScriptDetected,
      'narrative_repair_applied': narrativeRepairApplied,
      'narrative_repair_reason': narrativeRepairReason,
      'requested_duration_seconds': requestedDurationSeconds,
      'duration_preset_label': durationPresetLabel,
      'script_word_count': scriptWordCount,
      'narration_word_count': narrationWordCount,
      'narration_text_preview': narrationTextPreview,
      'force_research_used': forceResearchUsed,
      'llm_call_count': llmCallCount,
      'research_call_count': researchCallCount,
      'script_call_count': scriptCallCount,
      'last_llm_error': lastLlmError,
      'last_llm_provider': lastLlmProvider,
      'last_llm_model': lastLlmModel,
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
      'visual_status': visualStatus,
      'visual_items': visualItems.map((item) => item.toJson()).toList(),
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
      'voice_outdated': voiceOutdated,
      'creation_mode': creationMode,
      'creation_mode_label': creationModeLabel,
      'input_topic': inputTopic,
      'input_idea': inputIdea,
      'input_script': inputScript,
      'input_niche': inputNiche,
      'input_language': inputLanguage,
      'input_tone': inputTone,
      'input_created_at': inputCreatedAt,
      'opportunity_data': opportunityData,
      'script_import_status': scriptImportStatus,
      'creation_warnings': creationWarnings,
      'content_format': contentFormat,
      'content_format_label': contentFormatLabel,
      'concrete_promise': concretePromise,
      'viewer_reason_to_watch': viewerReasonToWatch,
      'watchability_score': watchabilityScore,
      'needs_more_context': needsMoreContext,
      'missing_context_fields': missingContextFields,
      'opportunity_script_repair_applied': opportunityScriptRepairApplied,
      'opportunity_script_repair_reason': opportunityScriptRepairReason,
      'extra_context': extraContext,
      'watchability_positive_signals': watchabilityPositiveSignals,
      'watchability_negative_signals': watchabilityNegativeSignals,
    };
  }
}

class GenerationOpportunity {
  const GenerationOpportunity({
    required this.opportunityId,
    required this.title,
    required this.niche,
    required this.topic,
    required this.eventDate,
    required this.freshness,
    required this.whyNow,
    required this.angle,
    required this.suggestedVideoTitle,
    required this.suggestedHook,
    required this.targetEmotion,
    required this.curiosityGap,
    required this.contentType,
    required this.sourceUrls,
    required this.sourceTitles,
    required this.confidence,
    required this.riskLevel,
    required this.factCheckNeeded,
    required this.provider,
    required this.eventName,
    required this.eventType,
    required this.teams,
    required this.people,
    required this.keyPlayers,
    required this.competition,
    required this.concretePromise,
    required this.viewerReasonToWatch,
    required this.suggestedVideoAngle,
    required this.contentFormat,
    required this.contentFormatLabel,
    required this.missingContextFields,
    required this.needsMoreContext,
  });

  final String opportunityId;
  final String title;
  final String niche;
  final String topic;
  final String eventDate;
  final String freshness;
  final String whyNow;
  final String angle;
  final String suggestedVideoTitle;
  final String suggestedHook;
  final String targetEmotion;
  final String curiosityGap;
  final String contentType;
  final List<String> sourceUrls;
  final List<String> sourceTitles;
  final String confidence;
  final String riskLevel;
  final bool factCheckNeeded;
  final String provider;
  final String eventName;
  final String eventType;
  final List<String> teams;
  final List<String> people;
  final List<Map<String, dynamic>> keyPlayers;
  final String competition;
  final String concretePromise;
  final String viewerReasonToWatch;
  final String suggestedVideoAngle;
  final String contentFormat;
  final String contentFormatLabel;
  final List<String> missingContextFields;
  final bool needsMoreContext;

  factory GenerationOpportunity.fromJson(Map<String, dynamic> json) {
    return GenerationOpportunity(
      opportunityId: _string(json['opportunity_id']),
      title: _string(json['title']),
      niche: _string(json['niche']),
      topic: _string(json['topic']),
      eventDate: _string(json['event_date']),
      freshness: _string(json['freshness']),
      whyNow: _string(json['why_now']),
      angle: _string(json['angle']),
      suggestedVideoTitle: _string(json['suggested_video_title']),
      suggestedHook: _string(json['suggested_hook']),
      targetEmotion: _string(json['target_emotion']),
      curiosityGap: _string(json['curiosity_gap']),
      contentType: _string(json['content_type']),
      sourceUrls: _stringList(json['source_urls']),
      sourceTitles: _stringList(json['source_titles']),
      confidence: _string(json['confidence']),
      riskLevel: _string(json['risk_level']),
      factCheckNeeded: _bool(json['fact_check_needed']),
      provider: _string(json['provider']),
      eventName: _string(json['event_name']),
      eventType: _string(json['event_type']),
      teams: _stringList(json['teams']),
      people: _stringList(json['people']),
      keyPlayers: _mapList(json['key_players']),
      competition: _string(json['competition']),
      concretePromise: _string(json['concrete_promise']),
      viewerReasonToWatch: _string(json['viewer_reason_to_watch']),
      suggestedVideoAngle: _string(json['suggested_video_angle']),
      contentFormat: _string(json['content_format']),
      contentFormatLabel: _string(json['content_format_label']),
      missingContextFields: _stringList(json['missing_context_fields']),
      needsMoreContext: _bool(json['needs_more_context']),
    );
  }

  Map<String, dynamic> toJson() => {
    'opportunity_id': opportunityId,
    'title': title,
    'niche': niche,
    'topic': topic,
    'event_date': eventDate,
    'freshness': freshness,
    'why_now': whyNow,
    'angle': angle,
    'suggested_video_title': suggestedVideoTitle,
    'suggested_hook': suggestedHook,
    'target_emotion': targetEmotion,
    'curiosity_gap': curiosityGap,
    'content_type': contentType,
    'source_urls': sourceUrls,
    'source_titles': sourceTitles,
    'confidence': confidence,
    'risk_level': riskLevel,
    'fact_check_needed': factCheckNeeded,
    'provider': provider,
    'event_name': eventName,
    'event_type': eventType,
    'teams': teams,
    'people': people,
    'key_players': keyPlayers,
    'competition': competition,
    'concrete_promise': concretePromise,
    'viewer_reason_to_watch': viewerReasonToWatch,
    'suggested_video_angle': suggestedVideoAngle,
    'content_format': contentFormat,
    'content_format_label': contentFormatLabel,
    'missing_context_fields': missingContextFields,
    'needs_more_context': needsMoreContext,
  };
}

class GenerationOpportunitySearchResponse {
  const GenerationOpportunitySearchResponse({
    required this.provider,
    required this.fallbackUsed,
    required this.groundingUsed,
    required this.opportunities,
  });

  final String provider;
  final bool fallbackUsed;
  final bool groundingUsed;
  final List<GenerationOpportunity> opportunities;

  factory GenerationOpportunitySearchResponse.fromJson(
    Map<String, dynamic> json,
  ) {
    return GenerationOpportunitySearchResponse(
      provider: _string(json['provider']),
      fallbackUsed: _bool(json['fallback_used']),
      groundingUsed: _bool(json['grounding_used']),
      opportunities: _mapList(
        json['opportunities'],
      ).map(GenerationOpportunity.fromJson).toList(),
    );
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
    required this.groundingEnabled,
    required this.groundingSupported,
    required this.models,
    required this.limits,
  });

  final String engineMode;
  final String provider;
  final bool externalAiAvailable;
  final bool fallbackAvailable;
  final bool requireExternalAi;
  final bool geminiConfigured;
  final String geminiModel;
  final List<String> features;
  final bool groundingEnabled;
  final bool? groundingSupported;
  final Map<String, dynamic> models;
  final Map<String, dynamic> limits;

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
      features: _stringList(json['feature_names'] ?? json['features']),
      groundingEnabled: _bool(json['grounding_enabled']),
      groundingSupported: json['grounding_supported'] == null
          ? null
          : _bool(json['grounding_supported']),
      models: _map(json['models']),
      limits: _map(json['limits']),
    );
  }
}

class GenerationVisualItem {
  const GenerationVisualItem({
    required this.visualId,
    required this.order,
    required this.scriptLineIndex,
    required this.storyBeatId,
    required this.beatRole,
    required this.type,
    required this.query,
    required this.description,
    required this.suggestedPrompt,
    required this.source,
    required this.licenseLane,
    required this.mediaUrl,
    required this.thumbnailUrl,
    required this.mediaPath,
    required this.durationSeconds,
    required this.startAtSeconds,
    required this.endAtSeconds,
    required this.status,
    required this.notes,
    required this.riskNotes,
  });

  final String visualId;
  final int order;
  final int scriptLineIndex;
  final String storyBeatId;
  final String beatRole;
  final String type;
  final String query;
  final String description;
  final String suggestedPrompt;
  final String source;
  final String licenseLane;
  final String mediaUrl;
  final String thumbnailUrl;
  final String mediaPath;
  final num? durationSeconds;
  final num? startAtSeconds;
  final num? endAtSeconds;
  final String status;
  final String notes;
  final String riskNotes;

  factory GenerationVisualItem.fromJson(Map<String, dynamic> json) {
    return GenerationVisualItem(
      visualId: _string(json['visual_id']),
      order: _int(json['order']),
      scriptLineIndex: _int(json['script_line_index']),
      storyBeatId: _string(json['story_beat_id']),
      beatRole: _string(json['beat_role']),
      type: _string(json['type']).isEmpty
          ? 'placeholder'
          : _string(json['type']),
      query: _string(json['query']),
      description: _string(json['description']),
      suggestedPrompt: _string(json['suggested_prompt']),
      source: _string(json['source']).isEmpty
          ? 'placeholder'
          : _string(json['source']),
      licenseLane: _string(json['license_lane']).isEmpty
          ? 'unknown'
          : _string(json['license_lane']),
      mediaUrl: _string(json['media_url']),
      thumbnailUrl: _string(json['thumbnail_url']),
      mediaPath: _string(json['media_path']),
      durationSeconds: _num(json['duration_seconds']),
      startAtSeconds: _num(json['start_at_seconds']),
      endAtSeconds: _num(json['end_at_seconds']),
      status: _string(json['status']).isEmpty
          ? 'suggestion'
          : _string(json['status']),
      notes: _string(json['notes']),
      riskNotes: _string(json['risk_notes']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'visual_id': visualId,
      'order': order,
      'script_line_index': scriptLineIndex,
      'story_beat_id': storyBeatId,
      'beat_role': beatRole,
      'type': type,
      'query': query,
      'description': description,
      'suggested_prompt': suggestedPrompt,
      'source': source,
      'license_lane': licenseLane,
      'media_url': mediaUrl,
      'thumbnail_url': thumbnailUrl,
      'media_path': mediaPath,
      'duration_seconds': durationSeconds,
      'start_at_seconds': startAtSeconds,
      'end_at_seconds': endAtSeconds,
      'status': status,
      'notes': notes,
      'risk_notes': riskNotes,
    };
  }
}

class GenerationStockSearchResponse {
  const GenerationStockSearchResponse({
    required this.provider,
    required this.available,
    required this.fallbackUsed,
    required this.results,
  });

  final String provider;
  final bool available;
  final bool fallbackUsed;
  final List<GenerationStockMedia> results;

  factory GenerationStockSearchResponse.fromJson(Map<String, dynamic> json) {
    return GenerationStockSearchResponse(
      provider: _string(json['provider']),
      available: _bool(json['available']),
      fallbackUsed: _bool(json['fallback_used']),
      results: _mapList(
        json['results'],
      ).map(GenerationStockMedia.fromJson).toList(),
    );
  }
}

class GenerationStockMedia {
  const GenerationStockMedia({
    required this.mediaId,
    required this.source,
    required this.title,
    required this.description,
    required this.thumbnailUrl,
    required this.mediaUrl,
    required this.photographer,
    required this.credit,
    required this.licenseLane,
  });

  final String mediaId;
  final String source;
  final String title;
  final String description;
  final String thumbnailUrl;
  final String mediaUrl;
  final String photographer;
  final String credit;
  final String licenseLane;

  factory GenerationStockMedia.fromJson(Map<String, dynamic> json) {
    return GenerationStockMedia(
      mediaId: _string(json['media_id']),
      source: _string(json['source']),
      title: _string(json['title']),
      description: _string(json['description']),
      thumbnailUrl: _string(json['thumbnail_url']),
      mediaUrl: _string(json['media_url']),
      photographer: _string(json['photographer']),
      credit: _string(json['credit']),
      licenseLane: _string(json['license_lane']).isEmpty
          ? 'unknown'
          : _string(json['license_lane']),
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

int _int(Object? value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? 0;
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
