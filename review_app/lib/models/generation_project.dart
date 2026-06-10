class GenerationIdea {
  const GenerationIdea({
    required this.title,
    required this.angle,
    required this.hook,
    required this.whyItMightWork,
    required this.riskLevel,
    required this.suggestedHashtags,
    required this.niche,
    required this.topic,
    required this.language,
    required this.tone,
  });

  final String title;
  final String angle;
  final String hook;
  final String whyItMightWork;
  final String riskLevel;
  final List<String> suggestedHashtags;
  final String niche;
  final String topic;
  final String language;
  final String tone;

  factory GenerationIdea.fromJson(Map<String, dynamic> json) {
    return GenerationIdea(
      title: _string(json['title']),
      angle: _string(json['angle']),
      hook: _string(json['hook']),
      whyItMightWork: _string(json['why_it_might_work']),
      riskLevel: _string(json['risk_level']),
      suggestedHashtags: _stringList(json['suggested_hashtags']),
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

num? _num(Object? value) {
  if (value is num) return value;
  return num.tryParse(value?.toString() ?? '');
}

List<String> _stringList(Object? value) {
  if (value is! List) return const [];
  return value
      .map((item) => item.toString())
      .where((item) => item.isNotEmpty)
      .toList();
}

List<Map<String, dynamic>> _mapList(Object? value) {
  if (value is! List) return const [];
  return value.whereType<Map>().map((item) {
    return item.map((key, value) => MapEntry(key.toString(), value));
  }).toList();
}
