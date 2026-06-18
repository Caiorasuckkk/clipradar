import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:audioplayers/audioplayers.dart';

import '../core/api_client.dart';
import '../models/generation_project.dart';
import 'generation_render_screen.dart';
import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import '../widgets/df_button.dart';
import '../widgets/df_card.dart';
import '../widgets/df_page_scaffold.dart';
import '../widgets/df_section_header.dart';
import '../widgets/df_status_chip.dart';

enum _GenerationTab { create, ideas, script, voice, visual, projects }

class GenerationScreen extends StatefulWidget {
  const GenerationScreen({
    super.key,
    required this.onOpenCuts,
    required this.onOpenAnalytics,
  });

  final VoidCallback onOpenCuts;
  final VoidCallback onOpenAnalytics;

  @override
  State<GenerationScreen> createState() => _GenerationScreenState();
}

class _GenerationScreenState extends State<GenerationScreen> {
  final ApiClient _api = ApiClient();
  final _nicheController = TextEditingController(text: 'futebol');
  final _topicController = TextEditingController();
  final _titleController = TextEditingController();
  final _hookController = TextEditingController();
  final _scriptController = TextEditingController();
  final _ctaController = TextEditingController();
  final _hashtagsController = TextEditingController();
  final _visualController = TextEditingController();
  final AudioPlayer _audioPlayer = AudioPlayer();

  _GenerationTab _tab = _GenerationTab.create;
  String _tone = 'curioso';
  String _language = 'pt-BR';
  String _scriptDepth = 'normal';
  String _narrativeStyle = 'dramatic';
  int _duration = 60;
  bool _loadingIdeas = false;
  bool _loadingScript = false;
  bool _loadingProjects = true;
  bool _loadingVoices = true;
  bool _loadingEngine = true;
  bool _savingProject = false;
  bool _regeneratingScript = false;
  bool _generatingVoice = false;
  bool _updatingVisuals = false;
  bool _playingVoice = false;
  bool _creatingProject = false;
  bool _searchingOpportunities = false;
  String? _error;
  GenerationIdea? _selectedIdea;
  GenerationScript? _script;
  GenerationProject? _selectedProject;
  GenerationVoicesResponse? _voicesResponse;
  GenerationEngineStatus? _engineStatus;
  String _selectedVoice = 'pt-BR-AntonioNeural';
  String _voiceSpeed = 'Normal';
  List<GenerationIdea> _ideas = const [];
  List<GenerationProject> _projects = const [];
  GenerationOpportunitySearchResponse? _opportunitySearch;

  @override
  void initState() {
    super.initState();
    _loadEngineStatus();
    _loadProjects();
    _loadVoices();
    _audioPlayer.onPlayerComplete.listen((_) {
      if (mounted) setState(() => _playingVoice = false);
    });
  }

  Future<void> _loadEngineStatus() async {
    try {
      final status = await _api.fetchGenerationEngineStatus();
      if (!mounted) return;
      setState(() {
        _engineStatus = status;
        _loadingEngine = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadingEngine = false;
      });
    }
  }

  @override
  void dispose() {
    _nicheController.dispose();
    _topicController.dispose();
    _titleController.dispose();
    _hookController.dispose();
    _scriptController.dispose();
    _ctaController.dispose();
    _hashtagsController.dispose();
    _visualController.dispose();
    _audioPlayer.dispose();
    super.dispose();
  }

  Future<void> _loadVoices() async {
    try {
      final voices = await _api.getGenerationVoices();
      if (!mounted) return;
      setState(() {
        _voicesResponse = voices;
        _loadingVoices = false;
        if (voices.voices.isNotEmpty) {
          _selectedVoice = voices.voices.first.name;
        }
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadingVoices = false;
        _error = 'Não foi possível carregar as vozes. Confira o backend.';
      });
    }
  }

  Future<void> _loadProjects() async {
    setState(() {
      _loadingProjects = true;
      _error = null;
    });
    try {
      final projects = await _api.getGenerationProjects();
      if (!mounted) return;
      setState(() {
        _projects = projects;
        _loadingProjects = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error =
            'Não foi possível carregar projetos. Confira se o backend está rodando.';
        _loadingProjects = false;
      });
    }
  }

  Future<void> _generateIdeas() async {
    if (_loadingIdeas) return;
    setState(() {
      _loadingIdeas = true;
      _error = null;
    });
    try {
      final ideas = await _api.generateIdeas(
        niche: _nicheController.text,
        topic: _topicController.text,
        language: _language,
        tone: _tone,
      );
      if (!mounted) return;
      setState(() {
        _ideas = ideas;
        _loadingIdeas = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = 'Não foi possível gerar ideias localmente. Confira o backend.';
        _loadingIdeas = false;
      });
    }
  }

  Future<void> _createFromIdea(Map<String, dynamic> values) async {
    if (_creatingProject) return;
    setState(() {
      _creatingProject = true;
      _error = null;
    });
    try {
      final project = await _api.createGenerationProjectFromIdea(
        idea: values['idea']?.toString() ?? '',
        niche: values['niche']?.toString() ?? '',
        language: values['language']?.toString() ?? 'pt-BR',
        tone: values['tone']?.toString() ?? 'curioso',
        durationSeconds: values['duration_seconds'] as int? ?? 90,
        scriptDepth: values['script_depth']?.toString() ?? 'normal',
        narrativeStyle: values['narrative_style']?.toString() ?? 'dramatic',
        contentFormat: values['content_format']?.toString() ?? 'manual_topic',
        extraContext: values['extra_context']?.toString() ?? '',
        autoGenerateScript: values['auto_generate_script'] != false,
        autoGenerateVoice: values['auto_generate_voice'] == true,
        autoSuggestVisuals: values['auto_suggest_visuals'] == true,
      );
      if (!mounted) return;
      await _loadProjects();
      if (!mounted) return;
      setState(() => _creatingProject = false);
      _openProject(project);
      _snack('Projeto criado a partir da sua ideia.');
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _creatingProject = false;
        _error = 'Não foi possível criar o projeto a partir da ideia.';
      });
    }
  }

  Future<void> _createFromReadyScript(Map<String, dynamic> values) async {
    if (_creatingProject) return;
    setState(() {
      _creatingProject = true;
      _error = null;
    });
    try {
      final project = await _api.createGenerationProjectFromScript(
        script: values['script']?.toString() ?? '',
        title: values['title']?.toString() ?? '',
        niche: values['niche']?.toString() ?? '',
        language: values['language']?.toString() ?? 'pt-BR',
        tone: values['tone']?.toString() ?? 'curioso',
        durationSeconds: values['duration_seconds'] as int? ?? 90,
        autoGenerateVoice: values['auto_generate_voice'] == true,
        autoSuggestVisuals: values['auto_suggest_visuals'] != false,
      );
      if (!mounted) return;
      await _loadProjects();
      if (!mounted) return;
      setState(() => _creatingProject = false);
      _openProject(project);
      _snack('Roteiro importado para revisão.');
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _creatingProject = false;
        _error = 'Não foi possível importar o roteiro.';
      });
    }
  }

  Future<void> _searchOpportunities(Map<String, dynamic> values) async {
    if (_searchingOpportunities) return;
    setState(() {
      _searchingOpportunities = true;
      _error = null;
    });
    try {
      final result = await _api.searchGenerationOpportunities(
        niche: values['niche']?.toString() ?? '',
        query: values['query']?.toString() ?? '',
        language: values['language']?.toString() ?? 'pt-BR',
        timeWindow: values['time_window']?.toString() ?? 'week',
        region: values['region']?.toString() ?? 'BR',
        count: values['count'] as int? ?? 5,
      );
      if (!mounted) return;
      setState(() {
        _opportunitySearch = result;
        _searchingOpportunities = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _searchingOpportunities = false;
        _error = 'Não foi possível buscar oportunidades agora.';
      });
    }
  }

  Future<void> _createFromOpportunity(
    GenerationOpportunity opportunity, [
    String extraContext = '',
  ]) async {
    if (_creatingProject) return;
    setState(() => _creatingProject = true);
    try {
      final project = await _api.createGenerationProjectFromOpportunity(
        opportunity: opportunity,
        durationSeconds: _duration,
        extraContext: extraContext,
      );
      if (!mounted) return;
      await _loadProjects();
      if (!mounted) return;
      setState(() => _creatingProject = false);
      _openProject(project);
      _snack('Oportunidade transformada em projeto.');
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _creatingProject = false;
        _error = 'Não foi possível criar o projeto desta oportunidade.';
      });
    }
  }

  Future<void> _createOpportunityBatch(
    List<GenerationOpportunity> opportunities,
  ) async {
    if (_creatingProject || opportunities.isEmpty) return;
    setState(() => _creatingProject = true);
    try {
      final projects = await _api
          .createGenerationProjectsFromOpportunitiesBatch(
            opportunities: opportunities,
            durationSeconds: _duration,
          );
      if (!mounted) return;
      await _loadProjects();
      if (!mounted) return;
      setState(() => _creatingProject = false);
      if (projects.isNotEmpty) _openProject(projects.first);
      _snack('${projects.length} projetos criados.');
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _creatingProject = false;
        _error = 'Não foi possível criar os projetos selecionados.';
      });
    }
  }

  Future<void> _createScript(GenerationIdea idea) async {
    if (_loadingScript) return;
    setState(() {
      _selectedIdea = idea;
      _loadingScript = true;
      _error = null;
      _tab = _GenerationTab.script;
    });
    try {
      final script = await _api.generateScript(
        idea: idea.title,
        niche: idea.niche,
        durationSeconds: _duration,
        tone: _tone,
        language: _language,
        scriptDepth: _scriptDepth,
        narrativeStyle: _narrativeStyle,
      );
      if (!mounted) return;
      _applyScript(script);
      setState(() {
        _script = script;
        _loadingScript = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = 'Não foi possível criar roteiro. Confira o backend.';
        _loadingScript = false;
      });
    }
  }

  Future<void> _saveProject() async {
    if (_savingProject) return;
    setState(() {
      _savingProject = true;
      _error = null;
    });
    try {
      final project = await _api.createGenerationProject(
        _currentProjectPayload(),
      );
      if (!mounted) return;
      await _loadProjects();
      setState(() {
        _selectedProject = project;
        _savingProject = false;
        _tab = _GenerationTab.voice;
      });
      _snack('Projeto salvo.');
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = 'Não foi possível salvar o projeto.';
        _savingProject = false;
      });
    }
  }

  Future<void> _archiveProject(GenerationProject project) async {
    try {
      await _api.updateGenerationProject(
        projectId: project.projectId,
        payload: {...project.toJson(), 'status': 'archived'},
      );
      await _loadProjects();
    } catch (_) {
      if (!mounted) return;
      _snack('Não foi possível arquivar.');
    }
  }

  Future<void> _deleteProject(GenerationProject project) async {
    try {
      await _api.deleteGenerationProject(project.projectId);
      await _loadProjects();
    } catch (_) {
      if (!mounted) return;
      _snack('Não foi possível remover.');
    }
  }

  void _openRender(GenerationProject project) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => GenerationRenderScreen(api: _api, project: project),
      ),
    );
  }

  void _openProject(GenerationProject project) {
    final script = GenerationScript(
      title: project.title,
      hook: project.hook,
      scriptLines: project.scriptLines,
      cta: project.cta,
      hashtags: project.hashtags,
      visualContext: project.visualContext,
      factCheckNotes: project.factCheckNotes,
      factualBrief: project.factualBrief,
      researchBrief: project.researchBrief,
      researchCacheHit: project.researchCacheHit,
      sourceUrls: project.sourceUrls,
      sourceTitles: project.sourceTitles,
      groundingUsed: project.groundingUsed,
      groundingAvailable: project.groundingAvailable,
      searchQueries: project.searchQueries,
      factualGroundingUsed: project.factualGroundingUsed,
      factualGroundingConfidence: project.factualGroundingConfidence,
      specificityScore: project.specificityScore,
      scriptDepth: project.scriptDepth,
      scriptDepthLabel: project.scriptDepthLabel,
      narrativeStyle: project.narrativeStyle,
      narrativeStyleLabel: project.narrativeStyleLabel,
      narrativePlan: project.narrativePlan,
      storyBeats: project.storyBeats,
      claimEvidencePairs: project.claimEvidencePairs,
      depthScore: project.depthScore,
      narrativeScore: project.narrativeScore,
      retentionScore: project.retentionScore,
      shallowScriptDetected: project.shallowScriptDetected,
      narrativeRepairApplied: project.narrativeRepairApplied,
      narrativeRepairReason: project.narrativeRepairReason,
      requestedDurationSeconds: project.requestedDurationSeconds,
      durationPresetLabel: project.durationPresetLabel,
      scriptWordCount: project.scriptWordCount,
      narrationWordCount: project.narrationWordCount,
      narrationTextPreview: project.narrationTextPreview,
      forceResearchUsed: project.forceResearchUsed,
      llmCallCount: project.llmCallCount,
      researchCallCount: project.researchCallCount,
      scriptCallCount: project.scriptCallCount,
      lastLlmError: project.lastLlmError,
      lastLlmProvider: project.lastLlmProvider,
      lastLlmModel: project.lastLlmModel,
      estimatedDurationSeconds: project.estimatedDurationSeconds,
      voiceStyle: project.voiceStyle,
      pacing: project.pacing,
      engineMode: project.engineMode,
      provider: project.provider,
      fallbackUsed: project.fallbackUsed,
      scriptQualityScore: project.scriptQualityScore,
      scriptQualityTier: project.scriptQualityTier,
      scriptPositiveSignals: project.scriptPositiveSignals,
      scriptNegativeSignals: project.scriptNegativeSignals,
      scriptRejectReason: project.scriptRejectReason,
      niche: project.niche,
      language: project.language,
      tone: project.tone,
      status: project.status,
      contentFormat: project.contentFormat,
      contentFormatLabel: project.contentFormatLabel,
      concretePromise: project.concretePromise,
      viewerReasonToWatch: project.viewerReasonToWatch,
      watchabilityScore: project.watchabilityScore,
      needsMoreContext: project.needsMoreContext,
      missingContextFields: project.missingContextFields,
      watchabilityPositiveSignals: project.watchabilityPositiveSignals,
      watchabilityNegativeSignals: project.watchabilityNegativeSignals,
    );
    _applyScript(script);
    setState(() {
      _script = script;
      _selectedProject = project;
      _duration = (project.requestedDurationSeconds ?? _duration).toInt();
      _scriptDepth = project.scriptDepth;
      _narrativeStyle = project.narrativeStyle;
      _selectedIdea = null;
      _tab = _GenerationTab.script;
    });
  }

  Future<void> _regenerateCurrentScript({required bool forceResearch}) async {
    final project = _selectedProject ?? _firstActiveProject();
    if (project == null) {
      setState(() => _error = 'Salve ou abra um projeto antes de regenerar.');
      return;
    }
    if (_regeneratingScript) return;
    setState(() {
      _regeneratingScript = true;
      _error = null;
    });
    try {
      final updated = await _api.regenerateGenerationProjectScript(
        projectId: project.projectId,
        durationSeconds: _duration,
        forceResearch: forceResearch,
        scriptDepth: _scriptDepth,
        narrativeStyle: _narrativeStyle,
      );
      await _loadProjects();
      if (!mounted) return;
      _openProject(updated);
      setState(() {
        _selectedProject = updated;
        _regeneratingScript = false;
      });
      _snack(
        forceResearch
            ? 'Roteiro regenerado com nova pesquisa.'
            : 'Roteiro regenerado.',
      );
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Não foi possível regenerar o roteiro.';
        _regeneratingScript = false;
      });
    }
  }

  Future<void> _improveCurrentScript() async {
    final project = _selectedProject ?? _firstActiveProject();
    if (project == null) {
      setState(() => _error = 'Salve ou abra um projeto antes de melhorar.');
      return;
    }
    if (_regeneratingScript) return;
    setState(() {
      _regeneratingScript = true;
      _error = null;
    });
    try {
      final updated = await _api.improveGenerationProjectScript(
        projectId: project.projectId,
        durationSeconds: _duration,
        scriptDepth: _scriptDepth,
        narrativeStyle: _narrativeStyle,
      );
      await _loadProjects();
      if (!mounted) return;
      _openProject(updated);
      setState(() {
        _selectedProject = updated;
        _regeneratingScript = false;
      });
      _snack('Roteiro melhorado.');
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Não foi possível melhorar o roteiro.';
        _regeneratingScript = false;
      });
    }
  }

  Future<void> _generateVoice() async {
    final project = _selectedProject ?? _firstActiveProject();
    if (project == null) {
      setState(() => _error = 'Salve ou abra um projeto antes de gerar voz.');
      return;
    }
    setState(() {
      _generatingVoice = true;
      _error = null;
    });
    try {
      final updated = await _api.generateProjectVoice(
        projectId: project.projectId,
        voice: _selectedVoice,
        rate: _rateForSpeed(_voiceSpeed),
        pitch: '+0Hz',
      );
      await _loadProjects();
      if (!mounted) return;
      setState(() {
        _selectedProject = updated;
        _generatingVoice = false;
      });
      _snack('Narração pronta.');
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error =
            'Não foi possível gerar a narração. Verifique se edge-tts está instalado no backend.';
        _generatingVoice = false;
      });
    }
  }

  Future<void> _suggestVisuals() async {
    final project = _selectedProject ?? _firstActiveProject();
    if (project == null) {
      setState(() => _error = 'Escolha um projeto para montar o visual.');
      return;
    }
    if (_updatingVisuals) return;
    setState(() {
      _updatingVisuals = true;
      _error = null;
    });
    try {
      final updated = await _api.suggestGenerationVisuals(project.projectId);
      await _loadProjects();
      if (!mounted) return;
      setState(() {
        _selectedProject = updated;
        _updatingVisuals = false;
      });
      _snack('Sugestões visuais criadas.');
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Não foi possível sugerir visual.';
        _updatingVisuals = false;
      });
    }
  }

  Future<void> _saveVisualItem(
    GenerationVisualItem? original,
    Map<String, dynamic> item,
  ) async {
    final project = _selectedProject ?? _firstActiveProject();
    if (project == null || _updatingVisuals) return;
    setState(() {
      _updatingVisuals = true;
      _error = null;
    });
    try {
      final updated = original == null
          ? await _api.addGenerationVisual(
              projectId: project.projectId,
              item: item,
            )
          : await _api.updateGenerationVisuals(
              projectId: project.projectId,
              items: project.visualItems.map((visual) {
                if (visual.visualId == original.visualId) {
                  return {...visual.toJson(), ...item};
                }
                return visual.toJson();
              }).toList(),
            );
      await _loadProjects();
      if (!mounted) return;
      setState(() {
        _selectedProject = updated;
        _updatingVisuals = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Não foi possível salvar o item visual.';
        _updatingVisuals = false;
      });
    }
  }

  Future<void> _deleteVisualItem(GenerationVisualItem item) async {
    final project = _selectedProject ?? _firstActiveProject();
    if (project == null || _updatingVisuals) return;
    setState(() => _updatingVisuals = true);
    try {
      final updated = await _api.deleteGenerationVisual(
        projectId: project.projectId,
        visualId: item.visualId,
      );
      await _loadProjects();
      if (!mounted) return;
      setState(() {
        _selectedProject = updated;
        _updatingVisuals = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Não foi possível remover o item visual.';
        _updatingVisuals = false;
      });
    }
  }

  Future<void> _setVisualSelected(GenerationVisualItem item) async {
    await _changeVisualStatus(item, selected: true);
  }

  Future<void> _rejectVisual(GenerationVisualItem item) async {
    await _changeVisualStatus(item, selected: false);
  }

  Future<void> _changeVisualStatus(
    GenerationVisualItem item, {
    required bool selected,
  }) async {
    final project = _selectedProject ?? _firstActiveProject();
    if (project == null || _updatingVisuals) return;
    setState(() => _updatingVisuals = true);
    try {
      final updated = selected
          ? await _api.selectGenerationVisual(
              projectId: project.projectId,
              visualId: item.visualId,
            )
          : await _api.rejectGenerationVisual(
              projectId: project.projectId,
              visualId: item.visualId,
            );
      await _loadProjects();
      if (!mounted) return;
      setState(() {
        _selectedProject = updated;
        _updatingVisuals = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Não foi possível atualizar o item visual.';
        _updatingVisuals = false;
      });
    }
  }

  Future<void> _markVisualReady() async {
    final project = _selectedProject ?? _firstActiveProject();
    if (project == null || _updatingVisuals) return;
    setState(() => _updatingVisuals = true);
    try {
      final updated = await _api.markGenerationVisualsReady(project.projectId);
      await _loadProjects();
      if (!mounted) return;
      setState(() {
        _selectedProject = updated;
        _updatingVisuals = false;
      });
      _snack('Visual pronto para render futuro.');
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Não foi possível marcar visual como pronto.';
        _updatingVisuals = false;
      });
    }
  }

  Future<void> _searchStockForVisual() async {
    final project = _selectedProject ?? _firstActiveProject();
    if (project == null) {
      setState(() => _error = 'Escolha um projeto para buscar stock.');
      return;
    }
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      builder: (context) => _StockSearchSheet(
        initialQuery: project.visualItems.isNotEmpty
            ? project.visualItems.first.query
            : project.title,
        onSearch: (query) => _api.searchGenerationStockMedia(query: query),
        onUse: (media) {
          Navigator.of(context).pop();
          _saveVisualItem(null, {
            'type': 'broll',
            'query': media.title,
            'description': media.description,
            'source': 'pexels',
            'license_lane': 'safe',
            'media_url': media.mediaUrl,
            'thumbnail_url': media.thumbnailUrl,
            'status': 'selected',
            'notes': [
              media.photographer,
              media.credit,
            ].where((item) => item.trim().isNotEmpty).join(' · '),
          });
        },
      ),
    );
  }

  Future<void> _openVisualEditor(GenerationVisualItem? item) async {
    final result = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      builder: (context) => _VisualItemEditor(item: item),
    );
    if (result != null) {
      await _saveVisualItem(item, result);
    }
  }

  Future<void> _deleteVoice() async {
    final project = _selectedProject ?? _firstActiveProject();
    if (project == null) return;
    try {
      await _audioPlayer.stop();
      final updated = await _api.deleteProjectVoice(project.projectId);
      await _loadProjects();
      if (!mounted) return;
      setState(() {
        _selectedProject = updated;
        _playingVoice = false;
      });
      _snack('Narração removida.');
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Não foi possível remover a narração.');
    }
  }

  Future<void> _toggleVoicePreview() async {
    final project = _selectedProject ?? _firstActiveProject();
    if (project == null || project.voiceStatus != 'ready') {
      setState(() => _error = 'Áudio ainda não foi gerado.');
      return;
    }
    if (_playingVoice) {
      await _audioPlayer.pause();
      if (mounted) setState(() => _playingVoice = false);
      return;
    }
    await _audioPlayer.play(
      UrlSource(_api.generationVoiceAudioUrl(project.projectId)),
    );
    if (mounted) setState(() => _playingVoice = true);
  }

  GenerationProject? _firstActiveProject() {
    for (final project in _projects) {
      if (project.status != 'archived') return project;
    }
    return null;
  }

  void _applyScript(GenerationScript script) {
    _titleController.text = script.title;
    _hookController.text = script.hook;
    _scriptController.text = script.scriptLines.join('\n');
    _ctaController.text = script.cta;
    _hashtagsController.text = script.hashtags.join(' ');
    _visualController.text = script.visualContext.join('\n');
  }

  Map<String, dynamic> _currentProjectPayload() {
    return {
      'title': _titleController.text,
      'niche': _nicheController.text,
      'language': _language,
      'tone': _tone,
      'status': 'script',
      'idea': _selectedIdea?.title ?? _titleController.text,
      'hook': _hookController.text,
      'script_lines': _lines(_scriptController.text),
      'cta': _ctaController.text,
      'hashtags': _hashtagsController.text
          .split(RegExp(r'\s+'))
          .where((item) => item.isNotEmpty)
          .toList(),
      'visual_context': _lines(_visualController.text),
      'fact_check_notes': _script?.factCheckNotes ?? const <String>[],
      'factual_brief': _script?.factualBrief ?? const <String, dynamic>{},
      'research_brief': _script?.researchBrief ?? const <String, dynamic>{},
      'research_cache_hit': _script?.researchCacheHit ?? false,
      'source_urls': _script?.sourceUrls ?? const <String>[],
      'source_titles': _script?.sourceTitles ?? const <String>[],
      'grounding_used': _script?.groundingUsed ?? false,
      'grounding_available': _script?.groundingAvailable ?? false,
      'search_queries': _script?.searchQueries ?? const <String>[],
      'factual_grounding_used': _script?.factualGroundingUsed ?? false,
      'factual_grounding_confidence':
          _script?.factualGroundingConfidence ?? 'low',
      'specificity_score': _script?.specificityScore,
      'script_depth': _script?.scriptDepth ?? _scriptDepth,
      'script_depth_label':
          _script?.scriptDepthLabel ?? _depthLabel(_scriptDepth),
      'narrative_style': _script?.narrativeStyle ?? _narrativeStyle,
      'narrative_style_label':
          _script?.narrativeStyleLabel ?? _styleLabel(_narrativeStyle),
      'narrative_plan': _script?.narrativePlan ?? const <String, dynamic>{},
      'story_beats': _script?.storyBeats ?? const <Map<String, dynamic>>[],
      'claim_evidence_pairs':
          _script?.claimEvidencePairs ?? const <Map<String, dynamic>>[],
      'depth_score': _script?.depthScore,
      'narrative_score': _script?.narrativeScore,
      'retention_score': _script?.retentionScore,
      'shallow_script_detected': _script?.shallowScriptDetected ?? false,
      'narrative_repair_applied': _script?.narrativeRepairApplied ?? false,
      'narrative_repair_reason': _script?.narrativeRepairReason ?? '',
      'requested_duration_seconds':
          _script?.requestedDurationSeconds ?? _duration,
      'duration_preset_label':
          _script?.durationPresetLabel ?? _durationLabel(_duration),
      'script_word_count': _script?.scriptWordCount ?? 0,
      'narration_word_count': _script?.narrationWordCount ?? 0,
      'narration_text_preview': _script?.narrationTextPreview ?? '',
      'force_research_used': _script?.forceResearchUsed ?? false,
      'llm_call_count': _script?.llmCallCount ?? 0,
      'research_call_count': _script?.researchCallCount ?? 0,
      'script_call_count': _script?.scriptCallCount ?? 0,
      'last_llm_error': _script?.lastLlmError ?? '',
      'last_llm_provider': _script?.lastLlmProvider ?? '',
      'last_llm_model': _script?.lastLlmModel ?? '',
      'estimated_duration_seconds':
          _script?.estimatedDurationSeconds ?? _duration,
      'voice_style': _script?.voiceStyle ?? '',
      'pacing': _script?.pacing ?? '',
      'engine_mode':
          _script?.engineMode ?? _engineStatus?.engineMode ?? 'local',
      'provider': _script?.provider ?? _engineStatus?.provider ?? 'none',
      'fallback_used': _script?.fallbackUsed ?? false,
      'script_quality_score': _script?.scriptQualityScore,
      'script_quality_tier': _script?.scriptQualityTier ?? '',
      'script_positive_signals':
          _script?.scriptPositiveSignals ?? const <String>[],
      'script_negative_signals':
          _script?.scriptNegativeSignals ?? const <String>[],
      'script_reject_reason': _script?.scriptRejectReason ?? '',
      'content_format': _script?.contentFormat ?? 'manual_topic',
      'content_format_label': _script?.contentFormatLabel ?? 'Tema manual',
      'concrete_promise': _script?.concretePromise ?? '',
      'viewer_reason_to_watch': _script?.viewerReasonToWatch ?? '',
      'watchability_score': _script?.watchabilityScore,
      'needs_more_context': _script?.needsMoreContext ?? false,
      'missing_context_fields':
          _script?.missingContextFields ?? const <String>[],
      'watchability_positive_signals':
          _script?.watchabilityPositiveSignals ?? const <String>[],
      'watchability_negative_signals':
          _script?.watchabilityNegativeSignals ?? const <String>[],
    };
  }

  Future<void> _copyScript() async {
    final text = [
      _titleController.text,
      '',
      _hookController.text,
      '',
      _scriptController.text,
      '',
      _ctaController.text,
      '',
      _hashtagsController.text,
    ].where((item) => item.trim().isNotEmpty).join('\n');
    await Clipboard.setData(ClipboardData(text: text));
    _snack('Roteiro copiado.');
  }

  void _snack(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return DfPageScaffold(
      title: 'Geração',
      subtitle: 'Crie ideias, roteiros e projetos para shorts narrados.',
      children: [
        if (_error != null) ...[
          _InlineError(message: _error!),
          const SizedBox(height: 12),
        ],
        _PipelineStatus(
          loadingEngine: _loadingEngine,
          engineStatus: _engineStatus,
        ),
        const SizedBox(height: 14),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SegmentedButton<_GenerationTab>(
            segments: const [
              ButtonSegment(
                value: _GenerationTab.create,
                icon: Icon(Icons.add_circle_outline_rounded),
                label: Text('Criar'),
              ),
              ButtonSegment(
                value: _GenerationTab.ideas,
                icon: Icon(Icons.lightbulb_rounded),
                label: Text('Ideias'),
              ),
              ButtonSegment(
                value: _GenerationTab.script,
                icon: Icon(Icons.edit_note_rounded),
                label: Text('Roteiro'),
              ),
              ButtonSegment(
                value: _GenerationTab.voice,
                icon: Icon(Icons.graphic_eq_rounded),
                label: Text('Voz'),
              ),
              ButtonSegment(
                value: _GenerationTab.visual,
                icon: Icon(Icons.video_library_rounded),
                label: Text('Visual'),
              ),
              ButtonSegment(
                value: _GenerationTab.projects,
                icon: Icon(Icons.folder_copy_rounded),
                label: Text('Projetos'),
              ),
            ],
            selected: {_tab},
            onSelectionChanged: (value) => setState(() => _tab = value.first),
          ),
        ),
        const SizedBox(height: 14),
        switch (_tab) {
          _GenerationTab.create => _CreateSection(
            busy: _creatingProject,
            searching: _searchingOpportunities,
            opportunities: _opportunitySearch,
            duration: _duration,
            onDurationChanged: (value) => setState(() => _duration = value),
            onCreateIdea: _createFromIdea,
            onCreateScript: _createFromReadyScript,
            onSearch: _searchOpportunities,
            onCreateOpportunity: _createFromOpportunity,
            onCreateBatch: _createOpportunityBatch,
          ),
          _GenerationTab.ideas => _IdeasSection(
            nicheController: _nicheController,
            topicController: _topicController,
            tone: _tone,
            language: _language,
            duration: _duration,
            loading: _loadingIdeas,
            ideas: _ideas,
            onToneChanged: (value) => setState(() => _tone = value),
            onLanguageChanged: (value) => setState(() => _language = value),
            onDurationChanged: (value) => setState(() => _duration = value),
            onGenerate: _generateIdeas,
            onCreateScript: _createScript,
          ),
          _GenerationTab.script => _ScriptSection(
            loading: _loadingScript,
            saving: _savingProject,
            script: _script,
            titleController: _titleController,
            hookController: _hookController,
            scriptController: _scriptController,
            ctaController: _ctaController,
            hashtagsController: _hashtagsController,
            visualController: _visualController,
            onSave: _saveProject,
            onCopy: _copyScript,
            onRegenerate: () => _regenerateCurrentScript(forceResearch: false),
            onRegenerateResearch: () =>
                _regenerateCurrentScript(forceResearch: true),
            onImprove: _improveCurrentScript,
            regenerating: _regeneratingScript,
            duration: _duration,
            scriptDepth: _scriptDepth,
            narrativeStyle: _narrativeStyle,
            onDurationChanged: (value) => setState(() => _duration = value),
            onDepthChanged: (value) => setState(() => _scriptDepth = value),
            onStyleChanged: (value) => setState(() => _narrativeStyle = value),
          ),
          _GenerationTab.voice => _VoiceSection(
            loadingVoices: _loadingVoices,
            loadingProjects: _loadingProjects,
            generating: _generatingVoice,
            playing: _playingVoice,
            project: _selectedProject,
            projects: _projects
                .where((project) => project.status != 'archived')
                .toList(),
            voices: _voicesResponse?.voices ?? const [],
            voicesAvailable: _voicesResponse?.available ?? false,
            installHint: _voicesResponse?.installHint ?? '',
            selectedVoice: _selectedVoice,
            speed: _voiceSpeed,
            onProjectChanged: (project) {
              _audioPlayer.stop();
              setState(() {
                _selectedProject = project;
                _playingVoice = false;
              });
            },
            onVoiceChanged: (voice) => setState(() => _selectedVoice = voice),
            onSpeedChanged: (speed) => setState(() => _voiceSpeed = speed),
            onGenerate: _generateVoice,
            onTogglePreview: _toggleVoicePreview,
            onDeleteVoice: _deleteVoice,
          ),
          _GenerationTab.visual => _VisualSection(
            project: _selectedProject ?? _firstActiveProject(),
            updating: _updatingVisuals,
            onSuggest: _suggestVisuals,
            onSearchStock: _searchStockForVisual,
            onAdd: () => _openVisualEditor(null),
            onEdit: _openVisualEditor,
            onSelect: _setVisualSelected,
            onReject: _rejectVisual,
            onDelete: _deleteVisualItem,
            onMarkReady: _markVisualReady,
          ),
          _GenerationTab.projects => _ProjectsSection(
            loading: _loadingProjects,
            projects: _projects,
            onRefresh: _loadProjects,
            onOpen: _openProject,
            onArchive: _archiveProject,
            onDelete: _deleteProject,
            onRender: _openRender,
          ),
        },
        const SizedBox(height: 18),
        DfCard(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.movie_filter_rounded, color: AppColors.cyan),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  'Render continua em preparação. Para produção pronta agora, use Cortes.',
                  style: TextStyle(color: AppColors.secondaryText),
                ),
              ),
              TextButton(
                onPressed: widget.onOpenCuts,
                child: const Text('Cortes'),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _CreateSection extends StatefulWidget {
  const _CreateSection({
    required this.busy,
    required this.searching,
    required this.opportunities,
    required this.duration,
    required this.onDurationChanged,
    required this.onCreateIdea,
    required this.onCreateScript,
    required this.onSearch,
    required this.onCreateOpportunity,
    required this.onCreateBatch,
  });

  final bool busy;
  final bool searching;
  final GenerationOpportunitySearchResponse? opportunities;
  final int duration;
  final ValueChanged<int> onDurationChanged;
  final Future<void> Function(Map<String, dynamic>) onCreateIdea;
  final Future<void> Function(Map<String, dynamic>) onCreateScript;
  final Future<void> Function(Map<String, dynamic>) onSearch;
  final Future<void> Function(GenerationOpportunity, [String extraContext])
  onCreateOpportunity;
  final Future<void> Function(List<GenerationOpportunity>) onCreateBatch;

  @override
  State<_CreateSection> createState() => _CreateSectionState();
}

class _CreateSectionState extends State<_CreateSection> {
  final _idea = TextEditingController();
  final _script = TextEditingController();
  final _title = TextEditingController();
  final _niche = TextEditingController(text: 'futebol');
  final _query = TextEditingController();
  final _extraContext = TextEditingController();
  String _mode = 'manual_idea';
  String _tone = 'curioso';
  String _language = 'pt-BR';
  String _scriptDepth = 'normal';
  String _narrativeStyle = 'dramatic';
  String _timeWindow = 'week';
  String _region = 'BR';
  int _opportunityCount = 5;
  bool _ideaGenerateScript = true;
  bool _ideaGenerateVoice = false;
  bool _ideaSuggestVisuals = false;
  bool _scriptGenerateVoice = false;
  bool _scriptSuggestVisuals = true;
  final Set<String> _selectedOpportunities = {};

  @override
  void dispose() {
    _idea.dispose();
    _script.dispose();
    _title.dispose();
    _niche.dispose();
    _query.dispose();
    _extraContext.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final opportunities = widget.opportunities?.opportunities ?? const [];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const DfSectionHeader(
          title: 'Criar conteúdo',
          subtitle: 'Comece por uma ideia, um roteiro seu ou um tema em alta.',
        ),
        const SizedBox(height: 10),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SegmentedButton<String>(
            segments: const [
              ButtonSegment(
                value: 'manual_idea',
                icon: Icon(Icons.lightbulb_outline_rounded),
                label: Text('Minha ideia'),
              ),
              ButtonSegment(
                value: 'ready_script',
                icon: Icon(Icons.description_outlined),
                label: Text('Roteiro pronto'),
              ),
              ButtonSegment(
                value: 'opportunity',
                icon: Icon(Icons.trending_up_rounded),
                label: Text('Em alta'),
              ),
            ],
            selected: {_mode},
            onSelectionChanged: (values) => setState(() {
              _mode = values.first;
              _selectedOpportunities.clear();
            }),
          ),
        ),
        const SizedBox(height: 12),
        DfCard(
          child: switch (_mode) {
            'ready_script' => _readyScriptForm(),
            'opportunity' => _opportunityForm(opportunities),
            _ => _ideaForm(),
          },
        ),
      ],
    );
  }

  Widget _ideaForm() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Minha ideia', style: AppTextStyles.cardTitle),
        const SizedBox(height: 6),
        const Text(
          'Descreva o assunto e o DarkFlow prepara um roteiro editável.',
          style: TextStyle(color: AppColors.secondaryText),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _idea,
          minLines: 3,
          maxLines: 6,
          onChanged: (_) => setState(() {}),
          decoration: const InputDecoration(
            labelText: 'Ideia',
            hintText: 'Ex.: por que um detalhe tático mudou a final',
          ),
        ),
        const SizedBox(height: 10),
        _commonInputs(),
        const SizedBox(height: 10),
        TextField(
          controller: _extraContext,
          minLines: 2,
          maxLines: 5,
          decoration: const InputDecoration(
            labelText: 'Contexto extra (opcional)',
            hintText:
                'Ex: jogo México x África do Sul, jogadores principais, data, competição, ponto que quero destacar…',
            alignLabelWithHint: true,
          ),
        ),
        SwitchListTile.adaptive(
          contentPadding: EdgeInsets.zero,
          value: _ideaGenerateScript,
          title: const Text('Gerar roteiro agora'),
          onChanged: (value) => setState(() => _ideaGenerateScript = value),
        ),
        SwitchListTile.adaptive(
          contentPadding: EdgeInsets.zero,
          value: _ideaGenerateVoice,
          title: const Text('Gerar voz depois do roteiro'),
          onChanged: _ideaGenerateScript
              ? (value) => setState(() => _ideaGenerateVoice = value)
              : null,
        ),
        SwitchListTile.adaptive(
          contentPadding: EdgeInsets.zero,
          value: _ideaSuggestVisuals,
          title: const Text('Sugerir visual depois do roteiro'),
          onChanged: _ideaGenerateScript
              ? (value) => setState(() => _ideaSuggestVisuals = value)
              : null,
        ),
        const SizedBox(height: 14),
        SizedBox(
          width: double.infinity,
          child: DFPrimaryButton(
            label: widget.busy ? 'Criando...' : 'Criar vídeo com minha ideia',
            icon: Icons.auto_awesome_rounded,
            onPressed: widget.busy || _idea.text.trim().isEmpty
                ? null
                : () => widget.onCreateIdea({
                    'idea': _idea.text.trim(),
                    'niche': _niche.text.trim(),
                    'language': _language,
                    'tone': _tone,
                    'duration_seconds': widget.duration,
                    'script_depth': _scriptDepth,
                    'narrative_style': _narrativeStyle,
                    'content_format': _formatForIdea(_idea.text),
                    'extra_context': _extraContext.text.trim(),
                    'auto_generate_script': _ideaGenerateScript,
                    'auto_generate_voice': _ideaGenerateVoice,
                    'auto_suggest_visuals': _ideaSuggestVisuals,
                  }),
          ),
        ),
      ],
    );
  }

  Widget _readyScriptForm() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Roteiro pronto', style: AppTextStyles.cardTitle),
        const SizedBox(height: 6),
        const Text(
          'Importa o texto sem reescrever. Você revisa antes de voz e visual.',
          style: TextStyle(color: AppColors.secondaryText),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _title,
          decoration: const InputDecoration(labelText: 'Título opcional'),
        ),
        const SizedBox(height: 10),
        TextField(
          controller: _script,
          minLines: 8,
          maxLines: 16,
          onChanged: (_) => setState(() {}),
          decoration: const InputDecoration(
            labelText: 'Cole seu roteiro',
            alignLabelWithHint: true,
          ),
        ),
        const SizedBox(height: 10),
        _commonInputs(),
        SwitchListTile.adaptive(
          contentPadding: EdgeInsets.zero,
          value: _scriptGenerateVoice,
          title: const Text('Gerar voz automaticamente'),
          onChanged: (value) => setState(() => _scriptGenerateVoice = value),
        ),
        SwitchListTile.adaptive(
          contentPadding: EdgeInsets.zero,
          value: _scriptSuggestVisuals,
          title: const Text('Sugerir visual automaticamente'),
          onChanged: (value) => setState(() => _scriptSuggestVisuals = value),
        ),
        const SizedBox(height: 14),
        SizedBox(
          width: double.infinity,
          child: DFPrimaryButton(
            label: widget.busy
                ? 'Importando...'
                : 'Transformar roteiro em projeto',
            icon: Icons.upload_file_rounded,
            onPressed: widget.busy || _script.text.trim().isEmpty
                ? null
                : () => widget.onCreateScript({
                    'script': _script.text.trim(),
                    'title': _title.text.trim(),
                    'niche': _niche.text.trim(),
                    'language': _language,
                    'tone': _tone,
                    'duration_seconds': widget.duration,
                    'auto_generate_voice': _scriptGenerateVoice,
                    'auto_suggest_visuals': _scriptSuggestVisuals,
                  }),
          ),
        ),
      ],
    );
  }

  Widget _opportunityForm(List<GenerationOpportunity> opportunities) {
    final selected = opportunities
        .where((item) => _selectedOpportunities.contains(item.opportunityId))
        .take(5)
        .toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Em alta', style: AppTextStyles.cardTitle),
        const SizedBox(height: 6),
        const Text(
          'Encontre ângulos atuais. Sugestões sem fonte ficam marcadas para checagem.',
          style: TextStyle(color: AppColors.secondaryText),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _niche,
          decoration: const InputDecoration(labelText: 'Nicho'),
        ),
        const SizedBox(height: 10),
        DropdownButtonFormField<String>(
          initialValue: _language,
          decoration: const InputDecoration(labelText: 'Idioma'),
          items: const [
            DropdownMenuItem(value: 'pt-BR', child: Text('Português (BR)')),
            DropdownMenuItem(value: 'en', child: Text('English')),
            DropdownMenuItem(value: 'es', child: Text('Español')),
          ],
          onChanged: (value) => setState(() => _language = value ?? 'pt-BR'),
        ),
        const SizedBox(height: 10),
        TextField(
          controller: _query,
          decoration: const InputDecoration(
            labelText: 'Tema opcional',
            hintText: 'Ex.: estreia, tecnologia, história',
          ),
        ),
        const SizedBox(height: 10),
        DropdownButtonFormField<String>(
          initialValue: _timeWindow,
          decoration: const InputDecoration(labelText: 'Janela'),
          items: const [
            DropdownMenuItem(value: 'today', child: Text('Hoje')),
            DropdownMenuItem(value: 'week', child: Text('Esta semana')),
            DropdownMenuItem(value: 'month', child: Text('Este mês')),
            DropdownMenuItem(value: 'evergreen', child: Text('Evergreen')),
          ],
          onChanged: (value) => setState(() => _timeWindow = value ?? 'week'),
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: DropdownButtonFormField<String>(
                initialValue: _region,
                decoration: const InputDecoration(labelText: 'Região'),
                items: const [
                  DropdownMenuItem(value: 'BR', child: Text('Brasil')),
                  DropdownMenuItem(value: 'US', child: Text('EUA')),
                  DropdownMenuItem(value: 'GLOBAL', child: Text('Global')),
                ],
                onChanged: (value) => setState(() => _region = value ?? 'BR'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: DropdownButtonFormField<int>(
                initialValue: _opportunityCount,
                decoration: const InputDecoration(labelText: 'Quantidade'),
                items: const [
                  DropdownMenuItem(value: 3, child: Text('3')),
                  DropdownMenuItem(value: 5, child: Text('5')),
                  DropdownMenuItem(value: 10, child: Text('10')),
                ],
                onChanged: (value) =>
                    setState(() => _opportunityCount = value ?? 5),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        SizedBox(
          width: double.infinity,
          child: DFPrimaryButton(
            label: widget.searching ? 'Buscando...' : 'Buscar oportunidades',
            icon: Icons.search_rounded,
            onPressed: widget.searching
                ? null
                : () => widget.onSearch({
                    'niche': _niche.text.trim(),
                    'query': _query.text.trim(),
                    'language': _language,
                    'time_window': _timeWindow,
                    'region': _region,
                    'count': _opportunityCount,
                  }),
          ),
        ),
        if (widget.opportunities != null) ...[
          const SizedBox(height: 10),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              DfStatusChip(label: widget.opportunities!.provider),
              if (widget.opportunities!.fallbackUsed)
                const DfStatusChip(label: 'sugestões locais'),
              if (widget.opportunities!.groundingUsed)
                const DfStatusChip(label: 'pesquisa web', status: 'success'),
            ],
          ),
        ],
        if (opportunities.isEmpty && widget.opportunities != null) ...[
          const SizedBox(height: 12),
          const _InlineWarning(message: 'Nenhuma oportunidade encontrada.'),
        ],
        ...opportunities.map(_opportunityCard),
        if (selected.isNotEmpty) ...[
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: DFSecondaryButton(
              label: widget.busy
                  ? 'Criando lote...'
                  : 'Criar ${selected.length} selecionados',
              icon: Icons.playlist_add_rounded,
              onPressed: widget.busy
                  ? null
                  : () => widget.onCreateBatch(selected),
            ),
          ),
        ],
      ],
    );
  }

  Widget _opportunityCard(GenerationOpportunity opportunity) {
    final checked = _selectedOpportunities.contains(opportunity.opportunityId);
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.secondaryBackground,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Checkbox(
                value: checked,
                onChanged: (value) => setState(() {
                  if (value == true) {
                    if (_selectedOpportunities.length < 5) {
                      _selectedOpportunities.add(opportunity.opportunityId);
                    }
                  } else {
                    _selectedOpportunities.remove(opportunity.opportunityId);
                  }
                }),
              ),
              Expanded(
                child: Text(
                  opportunity.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.cardTitle,
                ),
              ),
            ],
          ),
          Text(
            opportunity.angle,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: AppColors.secondaryText),
          ),
          const SizedBox(height: 6),
          _LabelText(label: 'Por que agora', text: opportunity.whyNow),
          if (opportunity.suggestedHook.isNotEmpty) ...[
            const SizedBox(height: 6),
            _LabelText(label: 'Hook', text: opportunity.suggestedHook),
          ],
          if (opportunity.sourceTitles.isNotEmpty ||
              opportunity.sourceUrls.isNotEmpty) ...[
            const SizedBox(height: 6),
            _LabelText(
              label: 'Fontes',
              text: [
                ...opportunity.sourceTitles,
                ...opportunity.sourceUrls,
              ].take(3).join(' · '),
            ),
          ],
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              DfStatusChip(label: opportunity.freshness),
              DfStatusChip(label: 'confiança ${opportunity.confidence}'),
              if (opportunity.factCheckNeeded)
                const DfStatusChip(label: 'fact-check', status: 'warning'),
              if (opportunity.contentFormatLabel.isNotEmpty)
                DfStatusChip(label: opportunity.contentFormatLabel),
            ],
          ),
          if (opportunity.needsMoreContext) ...[
            const SizedBox(height: 10),
            const _InlineWarning(
              message:
                  'Essa oportunidade precisa de mais contexto para gerar um vídeo bom.',
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                DFSecondaryButton(
                  label: 'Adicionar contexto',
                  icon: Icons.add_comment_outlined,
                  onPressed: widget.busy
                      ? null
                      : () => _addOpportunityContext(opportunity),
                ),
                DFGhostButton(
                  label: 'Fazer nova pesquisa',
                  icon: Icons.refresh_rounded,
                  onPressed: widget.searching
                      ? null
                      : () => widget.onSearch({
                          'niche': _niche.text.trim(),
                          'query': _query.text.trim(),
                          'language': _language,
                          'time_window': _timeWindow,
                          'region': _region,
                          'count': _opportunityCount,
                        }),
                ),
              ],
            ),
          ],
          const SizedBox(height: 10),
          Align(
            alignment: Alignment.centerRight,
            child: DFSecondaryButton(
              label: widget.busy
                  ? 'Criando...'
                  : opportunity.needsMoreContext
                  ? 'Gerar mesmo assim'
                  : 'Criar projeto',
              icon: Icons.arrow_forward_rounded,
              onPressed: widget.busy
                  ? null
                  : () => widget.onCreateOpportunity(opportunity),
            ),
          ),
        ],
      ),
    );
  }

  Widget _commonInputs() {
    return Column(
      children: [
        TextField(
          controller: _niche,
          decoration: const InputDecoration(labelText: 'Nicho'),
        ),
        const SizedBox(height: 10),
        DropdownButtonFormField<String>(
          initialValue: _language,
          decoration: const InputDecoration(labelText: 'Idioma'),
          items: const [
            DropdownMenuItem(value: 'pt-BR', child: Text('Português (BR)')),
            DropdownMenuItem(value: 'en', child: Text('English')),
            DropdownMenuItem(value: 'es', child: Text('Español')),
          ],
          onChanged: (value) => setState(() => _language = value ?? 'pt-BR'),
        ),
        const SizedBox(height: 10),
        DropdownButtonFormField<String>(
          initialValue: _tone,
          decoration: const InputDecoration(labelText: 'Tom'),
          items: const [
            DropdownMenuItem(value: 'curioso', child: Text('Curioso')),
            DropdownMenuItem(value: 'dramático', child: Text('Dramático')),
            DropdownMenuItem(value: 'informativo', child: Text('Informativo')),
          ],
          onChanged: (value) => setState(() => _tone = value ?? 'curioso'),
        ),
        const SizedBox(height: 10),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: _ScriptDepthRow(
            value: _scriptDepth,
            onChanged: (value) => setState(() => _scriptDepth = value),
          ),
        ),
        const SizedBox(height: 10),
        _NarrativeStyleRow(
          value: _narrativeStyle,
          onChanged: (value) => setState(() => _narrativeStyle = value),
        ),
        const SizedBox(height: 10),
        Align(
          alignment: Alignment.centerLeft,
          child: _DurationRow(
            value: widget.duration,
            onChanged: widget.onDurationChanged,
          ),
        ),
      ],
    );
  }

  String _formatForIdea(String idea) {
    final normalized = idea.toLowerCase();
    if (normalized.contains('jogador') || normalized.contains('quem pode')) {
      return 'player_watchlist';
    }
    if (normalized.contains('top ') || normalized.contains('curiosidade')) {
      return 'top_list';
    }
    return 'manual_topic';
  }

  Future<void> _addOpportunityContext(GenerationOpportunity opportunity) async {
    final controller = TextEditingController();
    final value = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Adicionar contexto'),
        content: TextField(
          controller: controller,
          autofocus: true,
          minLines: 4,
          maxLines: 8,
          decoration: const InputDecoration(
            labelText: 'Evento, times, pessoas e observações',
            alignLabelWithHint: true,
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.of(dialogContext).pop(controller.text.trim()),
            child: const Text('Criar projeto'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (value != null && value.isNotEmpty) {
      await widget.onCreateOpportunity(opportunity, value);
    }
  }
}

class _PipelineStatus extends StatelessWidget {
  const _PipelineStatus({
    required this.loadingEngine,
    required this.engineStatus,
  });

  final bool loadingEngine;
  final GenerationEngineStatus? engineStatus;

  @override
  Widget build(BuildContext context) {
    final steps = [
      ('Ideias', Icons.lightbulb_rounded, 'Ativo', 'success'),
      ('Roteiro', Icons.edit_note_rounded, 'Ativo', 'success'),
      ('Voz', Icons.graphic_eq_rounded, 'Ativo', 'success'),
      ('Visual/B-roll', Icons.video_library_rounded, 'Ativo', 'success'),
      ('Render', Icons.smart_display_rounded, 'Em breve', ''),
    ];
    return DfCard(
      color: AppColors.surfaceAlt,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Pipeline de Geração', style: AppTextStyles.cardTitle),
          const SizedBox(height: 10),
          _EngineStatusLine(loading: loadingEngine, status: engineStatus),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: steps.map((step) {
              return _StepChip(
                label: step.$1,
                icon: step.$2,
                status: step.$3,
                statusKey: step.$4,
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}

class _VoiceSection extends StatelessWidget {
  const _VoiceSection({
    required this.loadingVoices,
    required this.loadingProjects,
    required this.generating,
    required this.playing,
    required this.project,
    required this.projects,
    required this.voices,
    required this.voicesAvailable,
    required this.installHint,
    required this.selectedVoice,
    required this.speed,
    required this.onProjectChanged,
    required this.onVoiceChanged,
    required this.onSpeedChanged,
    required this.onGenerate,
    required this.onTogglePreview,
    required this.onDeleteVoice,
  });

  final bool loadingVoices;
  final bool loadingProjects;
  final bool generating;
  final bool playing;
  final GenerationProject? project;
  final List<GenerationProject> projects;
  final List<GenerationVoice> voices;
  final bool voicesAvailable;
  final String installHint;
  final String selectedVoice;
  final String speed;
  final ValueChanged<GenerationProject> onProjectChanged;
  final ValueChanged<String> onVoiceChanged;
  final ValueChanged<String> onSpeedChanged;
  final VoidCallback onGenerate;
  final VoidCallback onTogglePreview;
  final VoidCallback onDeleteVoice;

  @override
  Widget build(BuildContext context) {
    if (loadingProjects || loadingVoices) {
      return const DfCard(
        child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    if (projects.isEmpty) {
      return const _EmptyCard(
        title: 'Escolha ou salve um roteiro antes de gerar voz',
        text:
            'Crie um roteiro, salve como projeto e volte aqui para gerar a narração.',
      );
    }
    final selected =
        project != null &&
            projects.any((item) => item.projectId == project!.projectId)
        ? project
        : projects.first;
    final scriptPreview = [
      selected?.hook ?? '',
      ...(selected?.scriptLines ?? const <String>[]).take(3),
      selected?.cta ?? '',
    ].where((line) => line.trim().isNotEmpty).join('\n');
    return DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const DfSectionHeader(
            title: 'Voz',
            subtitle: 'Gere e ouça uma narração local para o projeto salvo.',
          ),
          DropdownButtonFormField<String>(
            initialValue: selected?.projectId,
            decoration: const InputDecoration(labelText: 'Projeto'),
            items: projects.map((item) {
              return DropdownMenuItem(
                value: item.projectId,
                child: Text(
                  item.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              );
            }).toList(),
            onChanged: (value) {
              for (final item in projects) {
                if (item.projectId == value) {
                  onProjectChanged(item);
                  break;
                }
              }
            },
          ),
          const SizedBox(height: 12),
          Text(
            selected?.title ?? 'Projeto',
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: AppTextStyles.cardTitle,
          ),
          const SizedBox(height: 8),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.secondaryBackground,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.border),
            ),
            child: Text(
              scriptPreview.isEmpty ? 'Roteiro vazio.' : scriptPreview,
              maxLines: 6,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: AppColors.secondaryText),
            ),
          ),
          const SizedBox(height: 12),
          if (!voicesAvailable)
            _InlineWarning(
              message: installHint.isEmpty
                  ? 'edge-tts não está disponível no backend.'
                  : installHint,
            ),
          if (!voicesAvailable) const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            initialValue: voices.any((voice) => voice.name == selectedVoice)
                ? selectedVoice
                : (voices.isNotEmpty ? voices.first.name : null),
            decoration: const InputDecoration(labelText: 'Voz'),
            items: voices.map((voice) {
              return DropdownMenuItem(
                value: voice.name,
                child: Text('${voice.label} • ${voice.locale}'),
              );
            }).toList(),
            onChanged: (value) {
              if (value != null) onVoiceChanged(value);
            },
          ),
          const SizedBox(height: 12),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'Lenta', label: Text('Lenta')),
              ButtonSegment(value: 'Normal', label: Text('Normal')),
              ButtonSegment(value: 'Rápida', label: Text('Rápida')),
            ],
            selected: {speed},
            onSelectionChanged: (values) => onSpeedChanged(values.first),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              DfStatusChip(
                label: _voiceStatusLabel(selected?.voiceStatus ?? 'none'),
                status: selected?.voiceStatus == 'ready'
                    ? 'success'
                    : selected?.voiceStatus == 'failed'
                    ? 'failed'
                    : selected?.voiceStatus == 'generating'
                    ? 'running'
                    : '',
              ),
              if ((selected?.voiceDurationSeconds ?? 0) > 0)
                DfStatusChip(
                  label: '${selected!.voiceDurationSeconds!.round()}s',
                ),
            ],
          ),
          if ((selected?.voiceError ?? '').isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              selected!.voiceError,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: AppColors.danger),
            ),
          ],
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              DFPrimaryButton(
                label: generating ? 'Gerando...' : 'Gerar narração',
                icon: Icons.record_voice_over_rounded,
                onPressed: generating || !voicesAvailable ? null : onGenerate,
              ),
              if (selected?.voiceStatus == 'ready')
                DFSecondaryButton(
                  label: playing ? 'Pausar' : 'Ouvir narração',
                  icon: playing
                      ? Icons.pause_rounded
                      : Icons.play_arrow_rounded,
                  onPressed: onTogglePreview,
                ),
              if (selected?.voiceStatus == 'ready')
                DFGhostButton(
                  label: 'Remover narração',
                  icon: Icons.delete_outline_rounded,
                  onPressed: onDeleteVoice,
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _EngineStatusLine extends StatelessWidget {
  const _EngineStatusLine({required this.loading, required this.status});

  final bool loading;
  final GenerationEngineStatus? status;

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Text('Carregando engine...', style: AppTextStyles.muted);
    }
    final engine = status?.engineMode ?? 'local';
    final provider = status?.provider ?? 'none';
    final fallbackText = status?.fallbackAvailable == true
        ? 'fallback local disponível'
        : 'sem fallback';
    final grounding = status?.groundingEnabled == true
        ? 'pesquisa ligada'
        : 'pesquisa desligada';
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        DfStatusChip(
          label: engine == 'canal_dark' ? 'Canal Dark Engine' : 'Local Engine',
          status: engine == 'canal_dark' ? 'running' : 'success',
        ),
        DfStatusChip(label: 'provider: $provider'),
        DfStatusChip(label: grounding),
        DfStatusChip(label: fallbackText),
        if (status?.externalAiAvailable == true)
          const DfStatusChip(label: 'Gemini ativo', status: 'success')
        else
          const DfStatusChip(label: 'sem IA externa'),
      ],
    );
  }
}

class _IdeasSection extends StatelessWidget {
  const _IdeasSection({
    required this.nicheController,
    required this.topicController,
    required this.tone,
    required this.language,
    required this.duration,
    required this.loading,
    required this.ideas,
    required this.onToneChanged,
    required this.onLanguageChanged,
    required this.onDurationChanged,
    required this.onGenerate,
    required this.onCreateScript,
  });

  final TextEditingController nicheController;
  final TextEditingController topicController;
  final String tone;
  final String language;
  final int duration;
  final bool loading;
  final List<GenerationIdea> ideas;
  final ValueChanged<String> onToneChanged;
  final ValueChanged<String> onLanguageChanged;
  final ValueChanged<int> onDurationChanged;
  final VoidCallback onGenerate;
  final ValueChanged<GenerationIdea> onCreateScript;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        DfCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const DfSectionHeader(
                title: 'Ideias',
                subtitle:
                    'Gere ângulos com engine local ou Canal Dark, com fallback seguro.',
              ),
              TextField(
                controller: nicheController,
                decoration: const InputDecoration(labelText: 'Nicho'),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: topicController,
                decoration: const InputDecoration(labelText: 'Tema opcional'),
              ),
              const SizedBox(height: 12),
              _OptionRow(
                label: 'Tom',
                value: tone,
                values: const [
                  'curioso',
                  'polêmico',
                  'didático',
                  'sério',
                  'leve',
                ],
                onChanged: onToneChanged,
              ),
              const SizedBox(height: 10),
              _OptionRow(
                label: 'Idioma',
                value: language,
                values: const ['pt-BR', 'en', 'es'],
                onChanged: onLanguageChanged,
              ),
              const SizedBox(height: 10),
              _DurationRow(value: duration, onChanged: onDurationChanged),
              const SizedBox(height: 14),
              SizedBox(
                width: double.infinity,
                child: DFPrimaryButton(
                  label: loading ? 'Gerando...' : 'Gerar ideias',
                  icon: Icons.auto_awesome_rounded,
                  onPressed: loading ? null : onGenerate,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        if (ideas.isEmpty)
          const _EmptyCard(
            title: 'Nenhuma ideia gerada ainda',
            text: 'Escolha um nicho e gere ideias locais para começar.',
          )
        else
          ...ideas.map(
            (idea) => _IdeaCard(idea: idea, onCreateScript: onCreateScript),
          ),
      ],
    );
  }
}

class _ScriptSection extends StatelessWidget {
  const _ScriptSection({
    required this.loading,
    required this.saving,
    required this.regenerating,
    required this.script,
    required this.titleController,
    required this.hookController,
    required this.scriptController,
    required this.ctaController,
    required this.hashtagsController,
    required this.visualController,
    required this.onSave,
    required this.onCopy,
    required this.onRegenerate,
    required this.onRegenerateResearch,
    required this.onImprove,
    required this.duration,
    required this.scriptDepth,
    required this.narrativeStyle,
    required this.onDurationChanged,
    required this.onDepthChanged,
    required this.onStyleChanged,
  });

  final bool loading;
  final bool saving;
  final bool regenerating;
  final GenerationScript? script;
  final TextEditingController titleController;
  final TextEditingController hookController;
  final TextEditingController scriptController;
  final TextEditingController ctaController;
  final TextEditingController hashtagsController;
  final TextEditingController visualController;
  final VoidCallback onSave;
  final VoidCallback onCopy;
  final VoidCallback onRegenerate;
  final VoidCallback onRegenerateResearch;
  final VoidCallback onImprove;
  final int duration;
  final String scriptDepth;
  final String narrativeStyle;
  final ValueChanged<int> onDurationChanged;
  final ValueChanged<String> onDepthChanged;
  final ValueChanged<String> onStyleChanged;

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const DfCard(
        child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    if (script == null && titleController.text.isEmpty) {
      return const _EmptyCard(
        title: 'Roteiro ainda não criado',
        text:
            'Gere ideias e toque em Criar roteiro para montar um rascunho editável.',
      );
    }
    return DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const DfSectionHeader(
            title: 'Roteiro',
            subtitle: 'Edite o rascunho antes de salvar o projeto.',
          ),
          _DurationRow(value: duration, onChanged: onDurationChanged),
          const SizedBox(height: 10),
          _ScriptDepthRow(value: scriptDepth, onChanged: onDepthChanged),
          const SizedBox(height: 10),
          _NarrativeStyleRow(value: narrativeStyle, onChanged: onStyleChanged),
          const SizedBox(height: 12),
          if (script != null) ...[
            _ScriptQualitySummary(script: script!),
            const SizedBox(height: 12),
          ],
          TextField(
            controller: titleController,
            decoration: const InputDecoration(labelText: 'Título'),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: hookController,
            decoration: const InputDecoration(labelText: 'Hook'),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: scriptController,
            minLines: 6,
            maxLines: 10,
            decoration: const InputDecoration(labelText: 'Linhas do roteiro'),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: ctaController,
            decoration: const InputDecoration(labelText: 'CTA'),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: hashtagsController,
            decoration: const InputDecoration(labelText: 'Hashtags'),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: visualController,
            minLines: 3,
            maxLines: 5,
            decoration: const InputDecoration(labelText: 'Contexto visual'),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              DFPrimaryButton(
                label: saving ? 'Salvando...' : 'Salvar projeto',
                icon: Icons.save_rounded,
                onPressed: saving ? null : onSave,
              ),
              DFSecondaryButton(
                label: 'Copiar roteiro',
                icon: Icons.copy_rounded,
                onPressed: onCopy,
              ),
              if (script != null)
                DFSecondaryButton(
                  label: regenerating ? 'Regenerando...' : 'Regenerar roteiro',
                  icon: Icons.refresh_rounded,
                  onPressed: regenerating ? null : onRegenerate,
                ),
              if (script != null)
                DFSecondaryButton(
                  label: regenerating ? 'Melhorando...' : 'Melhorar roteiro',
                  icon: Icons.auto_fix_high_rounded,
                  onPressed: regenerating ? null : onImprove,
                ),
              if (script != null)
                DFGhostButton(
                  label: 'Regenerar com nova pesquisa',
                  icon: Icons.travel_explore_rounded,
                  onPressed: regenerating ? null : onRegenerateResearch,
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _VisualSection extends StatelessWidget {
  const _VisualSection({
    required this.project,
    required this.updating,
    required this.onSuggest,
    required this.onSearchStock,
    required this.onAdd,
    required this.onEdit,
    required this.onSelect,
    required this.onReject,
    required this.onDelete,
    required this.onMarkReady,
  });

  final GenerationProject? project;
  final bool updating;
  final VoidCallback onSuggest;
  final VoidCallback onSearchStock;
  final VoidCallback onAdd;
  final ValueChanged<GenerationVisualItem?> onEdit;
  final ValueChanged<GenerationVisualItem> onSelect;
  final ValueChanged<GenerationVisualItem> onReject;
  final ValueChanged<GenerationVisualItem> onDelete;
  final VoidCallback onMarkReady;

  @override
  Widget build(BuildContext context) {
    final current = project;
    if (current == null) {
      return const _EmptyCard(
        title: 'Escolha um projeto para montar o visual',
        text: 'Abra ou salve um projeto antes de criar o plano de B-roll.',
      );
    }
    if (current.scriptLines.isEmpty) {
      return const _EmptyCard(
        title: 'Crie um roteiro antes de montar o visual',
        text: 'O plano visual usa roteiro, story beats e contexto de pesquisa.',
      );
    }
    final items = current.visualItems;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        DfCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              DfSectionHeader(title: 'Visual/B-roll', subtitle: current.title),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  DfStatusChip(label: _visualStatusLabel(current.visualStatus)),
                  DfStatusChip(label: _voiceStatusLabel(current.voiceStatus)),
                  if (current.voiceOutdated)
                    const DfStatusChip(
                      label: 'voz desatualizada',
                      status: 'warning',
                    ),
                  if (current.visualStatus == 'ready')
                    const DfStatusChip(
                      label: 'Pronto para render',
                      status: 'success',
                    ),
                  if ((current.requestedDurationSeconds ?? 0) > 0)
                    DfStatusChip(
                      label: '${current.requestedDurationSeconds!.round()}s',
                    ),
                ],
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  DFPrimaryButton(
                    label: updating ? 'Gerando...' : 'Sugerir visual',
                    icon: Icons.auto_awesome_motion_rounded,
                    onPressed: updating ? null : onSuggest,
                  ),
                  DFSecondaryButton(
                    label: 'Buscar stock',
                    icon: Icons.search_rounded,
                    onPressed: updating ? null : onSearchStock,
                  ),
                  DFSecondaryButton(
                    label: 'Adicionar item',
                    icon: Icons.add_rounded,
                    onPressed: updating ? null : onAdd,
                  ),
                  DFGhostButton(
                    label: 'Marcar visual pronto',
                    icon: Icons.check_circle_outline_rounded,
                    onPressed: updating || items.isEmpty ? null : onMarkReady,
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        if (items.isEmpty)
          const _EmptyCard(
            title: 'Nenhum item visual ainda',
            text: 'Toque em Sugerir visual para criar uma timeline inicial.',
          )
        else
          ...items.map(
            (item) => _VisualItemCard(
              item: item,
              scriptLine: _scriptLineFor(current, item),
              onEdit: () => onEdit(item),
              onSelect: () => onSelect(item),
              onReject: () => onReject(item),
              onDelete: () => onDelete(item),
            ),
          ),
      ],
    );
  }
}

class _VisualItemCard extends StatelessWidget {
  const _VisualItemCard({
    required this.item,
    required this.scriptLine,
    required this.onEdit,
    required this.onSelect,
    required this.onReject,
    required this.onDelete,
  });

  final GenerationVisualItem item;
  final String scriptLine;
  final VoidCallback onEdit;
  final VoidCallback onSelect;
  final VoidCallback onReject;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: DfCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    '#${item.order} · ${item.beatRole.isEmpty ? item.type : item.beatRole}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.cardTitle,
                  ),
                ),
                DfStatusChip(
                  label: _licenseLabel(item.licenseLane),
                  status: _licenseStatus(item.licenseLane),
                ),
              ],
            ),
            const SizedBox(height: 6),
            if (scriptLine.isNotEmpty)
              Text(
                scriptLine,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.muted,
              ),
            const SizedBox(height: 8),
            _LabelText(label: 'Query', text: item.query),
            if (item.description.isNotEmpty) ...[
              const SizedBox(height: 4),
              _LabelText(label: 'Descrição', text: item.description),
            ],
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                DfStatusChip(label: item.type),
                DfStatusChip(label: item.source),
                DfStatusChip(
                  label: item.status,
                  status: _visualItemStatus(item.status),
                ),
                if ((item.startAtSeconds ?? 0) >= 0 &&
                    (item.endAtSeconds ?? 0) > 0)
                  DfStatusChip(
                    label:
                        '${item.startAtSeconds?.round() ?? 0}s-${item.endAtSeconds?.round() ?? 0}s',
                  ),
              ],
            ),
            if (item.riskNotes.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                item.riskNotes,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: AppColors.warning),
              ),
            ],
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                DFSecondaryButton(
                  label: 'Editar',
                  icon: Icons.edit_rounded,
                  onPressed: onEdit,
                ),
                DFSecondaryButton(
                  label: 'Selecionar',
                  icon: Icons.check_rounded,
                  onPressed: onSelect,
                ),
                DFGhostButton(
                  label: 'Rejeitar',
                  icon: Icons.block_rounded,
                  onPressed: onReject,
                ),
                DFGhostButton(
                  label: 'Remover',
                  icon: Icons.delete_outline_rounded,
                  onPressed: onDelete,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ProjectsSection extends StatelessWidget {
  const _ProjectsSection({
    required this.loading,
    required this.projects,
    required this.onRefresh,
    required this.onOpen,
    required this.onArchive,
    required this.onDelete,
    required this.onRender,
  });

  final bool loading;
  final List<GenerationProject> projects;
  final VoidCallback onRefresh;
  final ValueChanged<GenerationProject> onOpen;
  final ValueChanged<GenerationProject> onArchive;
  final ValueChanged<GenerationProject> onDelete;
  final ValueChanged<GenerationProject> onRender;

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const DfCard(
        child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    final active = projects
        .where((project) => project.status != 'archived')
        .toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Expanded(
              child: DfSectionHeader(
                title: 'Projetos',
                subtitle: 'Rascunhos salvos localmente.',
              ),
            ),
            IconButton(
              onPressed: onRefresh,
              icon: const Icon(Icons.refresh_rounded),
            ),
          ],
        ),
        if (active.isEmpty)
          const _EmptyCard(
            title: 'Nenhum projeto salvo',
            text: 'Crie um roteiro e toque em Salvar projeto.',
          )
        else
          ...active.map(
            (project) => _ProjectCard(
              project: project,
              onOpen: onOpen,
              onArchive: onArchive,
              onDelete: onDelete,
              onRender: onRender,
            ),
          ),
      ],
    );
  }
}

class _IdeaCard extends StatelessWidget {
  const _IdeaCard({required this.idea, required this.onCreateScript});

  final GenerationIdea idea;
  final ValueChanged<GenerationIdea> onCreateScript;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: DfCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(idea.title, style: AppTextStyles.cardTitle),
                ),
                DfStatusChip(
                  label: idea.riskLevel == 'low' ? 'baixo risco' : 'atenção',
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              idea.hook,
              style: const TextStyle(color: AppColors.secondaryText),
            ),
            const SizedBox(height: 8),
            Text(idea.whyItMightWork, style: AppTextStyles.muted),
            if (idea.curiosityGap.isNotEmpty) ...[
              const SizedBox(height: 8),
              _LabelText(label: 'Lacuna', text: idea.curiosityGap),
            ],
            if (idea.visualDirection.isNotEmpty) ...[
              const SizedBox(height: 6),
              _LabelText(label: 'Visual', text: idea.visualDirection),
            ],
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                if (idea.targetEmotion.isNotEmpty)
                  DfStatusChip(label: idea.targetEmotion),
                if (idea.factCheckNeeded)
                  const DfStatusChip(label: 'fact-check', status: 'warning'),
                DfStatusChip(label: idea.engineMode),
                ...idea.suggestedHashtags
                    .take(4)
                    .map((tag) => DfStatusChip(label: tag)),
              ],
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: DFSecondaryButton(
                label: 'Criar roteiro',
                icon: Icons.edit_note_rounded,
                onPressed: () => onCreateScript(idea),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ProjectCard extends StatelessWidget {
  const _ProjectCard({
    required this.project,
    required this.onOpen,
    required this.onArchive,
    required this.onDelete,
    required this.onRender,
  });

  final GenerationProject project;
  final ValueChanged<GenerationProject> onOpen;
  final ValueChanged<GenerationProject> onArchive;
  final ValueChanged<GenerationProject> onDelete;
  final ValueChanged<GenerationProject> onRender;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: DfCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    project.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.cardTitle,
                  ),
                ),
                DfStatusChip(label: project.status),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              '${project.niche} • ${project.tone} • ${project.language}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.muted,
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                DfStatusChip(label: project.creationModeLabel),
                DfStatusChip(label: project.contentFormatLabel),
                if ((project.watchabilityScore ?? 0) > 0)
                  DfStatusChip(
                    label: 'assist. ${project.watchabilityScore}',
                    status: (project.watchabilityScore ?? 0) >= 7
                        ? 'success'
                        : 'warning',
                  ),
                if ((project.estimatedDurationSeconds ?? 0) > 0)
                  DfStatusChip(
                    label:
                        '${project.estimatedDurationSeconds!.round()}s estimados',
                  ),
                DfStatusChip(
                  label: project.scriptLines.isEmpty
                      ? 'sem roteiro'
                      : 'roteiro pronto',
                  status: project.scriptLines.isEmpty ? '' : 'success',
                ),
                DfStatusChip(
                  label: 'voz ${project.voiceStatus}',
                  status: project.voiceStatus == 'ready' ? 'success' : '',
                ),
                if (project.scriptQualityTier.isNotEmpty)
                  DfStatusChip(
                    label:
                        '${project.scriptQualityTier} ${project.scriptQualityScore ?? ''}',
                    status: _qualityStatus(project.scriptQualityTier),
                  ),
                DfStatusChip(label: project.engineMode),
                if (project.fallbackUsed) const DfStatusChip(label: 'fallback'),
                if (project.factCheckNotes.isNotEmpty)
                  const DfStatusChip(label: 'fact-check', status: 'warning'),
                if (project.voiceOutdated)
                  const DfStatusChip(
                    label: 'voz desatualizada',
                    status: 'warning',
                  ),
                if (project.visualStatus == 'draft')
                  const DfStatusChip(
                    label: 'visual em rascunho',
                    status: 'warning',
                  ),
                if (project.visualStatus == 'ready')
                  const DfStatusChip(label: 'visual pronto', status: 'success'),
                if (project.status == 'ready_for_render')
                  const DfStatusChip(
                    label: 'pronto para render',
                    status: 'success',
                  ),
                if (project.scriptImportStatus == 'needs_review')
                  const DfStatusChip(
                    label: 'roteiro precisa revisão',
                    status: 'warning',
                  ),
              ],
            ),
            if (project.creationWarnings.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                project.creationWarnings.first,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: AppColors.warning),
              ),
            ],
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                DFSecondaryButton(
                  label: 'Abrir',
                  icon: Icons.open_in_new_rounded,
                  onPressed: () => onOpen(project),
                ),
                if (project.voiceStatus == 'ready')
                  DFPrimaryButton(
                    label: project.renderStatus == 'ready'
                        ? 'Ver vídeo'
                        : 'Renderizar',
                    icon: Icons.movie_creation_rounded,
                    onPressed: () => onRender(project),
                  ),
                DFSecondaryButton(
                  label: 'Arquivar',
                  icon: Icons.archive_rounded,
                  onPressed: () => onArchive(project),
                ),
                DFGhostButton(
                  label: 'Remover',
                  icon: Icons.delete_outline_rounded,
                  onPressed: () => onDelete(project),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ScriptQualitySummary extends StatelessWidget {
  const _ScriptQualitySummary({required this.script});

  final GenerationScript script;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.secondaryBackground,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              DfStatusChip(
                label:
                    'score ${script.scriptQualityScore ?? '-'} · ${script.scriptQualityTier.isEmpty ? 'sem tier' : script.scriptQualityTier}',
                status: _qualityStatus(script.scriptQualityTier),
              ),
              DfStatusChip(label: script.engineMode),
              DfStatusChip(label: 'provider: ${script.provider}'),
              if (script.fallbackUsed) const DfStatusChip(label: 'fallback'),
              if (script.provider == 'gemini')
                const DfStatusChip(
                  label: 'Gemini + pesquisa',
                  status: 'success',
                ),
              if (script.researchCacheHit)
                const DfStatusChip(label: 'cache de pesquisa'),
              if (script.groundingUsed)
                const DfStatusChip(label: 'fatos aplicados', status: 'success'),
              if (script.factualGroundingConfidence == 'low')
                const DfStatusChip(
                  label: 'baixa confiança factual',
                  status: 'warning',
                ),
              if ((script.estimatedDurationSeconds ?? 0) > 0)
                DfStatusChip(
                  label: '${script.estimatedDurationSeconds!.round()}s',
                ),
              if ((script.specificityScore ?? 0) > 0)
                DfStatusChip(label: 'espec. ${script.specificityScore}'),
              DfStatusChip(label: script.scriptDepthLabel),
              DfStatusChip(label: script.narrativeStyleLabel),
              if ((script.depthScore ?? 0) > 0)
                DfStatusChip(label: 'depth ${script.depthScore}'),
              if ((script.narrativeScore ?? 0) > 0)
                DfStatusChip(label: 'narrativa ${script.narrativeScore}'),
              if ((script.retentionScore ?? 0) > 0)
                DfStatusChip(label: 'retenção ${script.retentionScore}'),
              if (script.shallowScriptDetected)
                const DfStatusChip(label: 'roteiro raso', status: 'warning'),
              if (script.narrativeRepairApplied)
                const DfStatusChip(
                  label: 'roteiro melhorado',
                  status: 'success',
                ),
              if (script.durationPresetLabel.isNotEmpty)
                DfStatusChip(label: script.durationPresetLabel),
              if (script.narrationWordCount > 0)
                DfStatusChip(label: '${script.narrationWordCount} palavras'),
              if (script.forceResearchUsed)
                const DfStatusChip(label: 'nova pesquisa', status: 'success'),
              DfStatusChip(label: script.contentFormatLabel),
              if ((script.watchabilityScore ?? 0) > 0)
                DfStatusChip(
                  label: 'assistibilidade ${script.watchabilityScore}',
                  status: (script.watchabilityScore ?? 0) >= 7
                      ? 'success'
                      : 'warning',
                ),
              if (script.concretePromise.isNotEmpty)
                const DfStatusChip(label: 'promessa clara', status: 'success'),
              if (script.needsMoreContext)
                const DfStatusChip(
                  label: 'precisa de contexto',
                  status: 'warning',
                ),
              if (script.watchabilityNegativeSignals.contains(
                'generic_sports_essay',
              ))
                const DfStatusChip(label: 'genérico demais', status: 'warning'),
              if ((script.watchabilityScore ?? 0) >= 7 &&
                  !script.needsMoreContext)
                const DfStatusChip(label: 'bom para postar', status: 'success'),
            ],
          ),
          if (script.concretePromise.isNotEmpty) ...[
            const SizedBox(height: 8),
            _LabelText(label: 'Promessa', text: script.concretePromise),
          ],
          if (script.viewerReasonToWatch.isNotEmpty) ...[
            const SizedBox(height: 6),
            _LabelText(
              label: 'Motivo para assistir',
              text: script.viewerReasonToWatch,
            ),
          ],
          if (script.voiceStyle.isNotEmpty || script.pacing.isNotEmpty) ...[
            const SizedBox(height: 8),
            _LabelText(
              label: 'Voz',
              text: [
                script.voiceStyle,
                script.pacing,
              ].where((item) => item.trim().isNotEmpty).join(' · '),
            ),
          ],
          if (script.factCheckNotes.isNotEmpty) ...[
            const SizedBox(height: 8),
            _LabelText(
              label: 'Fact-check',
              text: script.factCheckNotes.join(' '),
            ),
          ],
          if (script.researchBrief.isNotEmpty ||
              script.narrativePlan.isNotEmpty ||
              script.sourceUrls.isNotEmpty ||
              script.sourceTitles.isNotEmpty) ...[
            const SizedBox(height: 8),
            _ResearchBriefExpansion(script: script),
          ],
          if (script.scriptPositiveSignals.isNotEmpty) ...[
            const SizedBox(height: 8),
            _LabelText(
              label: 'Sinais bons',
              text: script.scriptPositiveSignals.take(4).join(', '),
            ),
          ],
          if (script.scriptNegativeSignals.isNotEmpty) ...[
            const SizedBox(height: 6),
            _LabelText(
              label: 'Ajustes',
              text: script.scriptNegativeSignals.take(4).join(', '),
            ),
          ],
        ],
      ),
    );
  }
}

class _LabelText extends StatelessWidget {
  const _LabelText({required this.label, required this.text});

  final String label;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Text.rich(
      TextSpan(
        children: [
          TextSpan(
            text: '$label: ',
            style: const TextStyle(
              color: AppColors.text,
              fontWeight: FontWeight.w800,
            ),
          ),
          TextSpan(
            text: text,
            style: const TextStyle(color: AppColors.secondaryText),
          ),
        ],
      ),
      maxLines: 3,
      overflow: TextOverflow.ellipsis,
    );
  }
}

class _ResearchBriefExpansion extends StatelessWidget {
  const _ResearchBriefExpansion({required this.script});

  final GenerationScript script;

  @override
  Widget build(BuildContext context) {
    final brief = script.researchBrief.isNotEmpty
        ? script.researchBrief
        : script.factualBrief;
    final entities = _asStringList(brief['key_entities']);
    final summary = [brief['summary'], brief['conflict'], brief['consequence']]
        .map((item) => item?.toString() ?? '')
        .where((item) => item.isNotEmpty)
        .toList();
    final plan = script.narrativePlan;
    final beats = script.storyBeats;
    return Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        tilePadding: EdgeInsets.zero,
        childrenPadding: EdgeInsets.zero,
        title: const Text(
          'Ver pesquisa/fatos',
          style: TextStyle(fontWeight: FontWeight.w800),
        ),
        children: [
          if (entities.isNotEmpty)
            _LabelText(label: 'Entidades', text: entities.take(6).join(', ')),
          if (summary.isNotEmpty) ...[
            const SizedBox(height: 6),
            _LabelText(label: 'Brief', text: summary.take(3).join(' ')),
          ],
          if (plan.isNotEmpty) ...[
            const SizedBox(height: 10),
            const Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Estrutura narrativa',
                style: TextStyle(fontWeight: FontWeight.w900),
              ),
            ),
            const SizedBox(height: 6),
            _LabelText(
              label: 'Pergunta central',
              text: _field(plan, 'central_question'),
            ),
            const SizedBox(height: 4),
            _LabelText(label: 'Conflito', text: _field(plan, 'conflict')),
            const SizedBox(height: 4),
            _LabelText(label: 'Detalhe', text: _field(plan, 'hidden_detail')),
            const SizedBox(height: 4),
            _LabelText(
              label: 'Consequência',
              text: _field(plan, 'consequence'),
            ),
            const SizedBox(height: 4),
            _LabelText(
              label: 'Pergunta final',
              text: _field(plan, 'closing_question'),
            ),
          ],
          if (beats.isNotEmpty) ...[
            const SizedBox(height: 6),
            _LabelText(
              label: 'Beats',
              text: beats
                  .take(5)
                  .map((beat) => '${beat['role']}: ${beat['content']}')
                  .join(' · '),
            ),
          ],
          if (script.sourceTitles.isNotEmpty) ...[
            const SizedBox(height: 6),
            _LabelText(
              label: 'Fontes',
              text: script.sourceTitles.take(3).join(' · '),
            ),
          ] else if (script.sourceUrls.isNotEmpty) ...[
            const SizedBox(height: 6),
            _LabelText(
              label: 'Fontes',
              text: script.sourceUrls.take(3).join(' · '),
            ),
          ],
          if (script.lastLlmError.isNotEmpty) ...[
            const SizedBox(height: 6),
            _LabelText(label: 'Fallback', text: script.lastLlmError),
          ],
        ],
      ),
    );
  }
}

List<String> _asStringList(Object? value) {
  if (value is! List) return const [];
  return value
      .map((item) => item.toString())
      .where((item) => item.isNotEmpty)
      .toList();
}

class _VisualItemEditor extends StatefulWidget {
  const _VisualItemEditor({required this.item});

  final GenerationVisualItem? item;

  @override
  State<_VisualItemEditor> createState() => _VisualItemEditorState();
}

class _VisualItemEditorState extends State<_VisualItemEditor> {
  late String _type;
  late String _source;
  late String _licenseLane;
  late final TextEditingController _query;
  late final TextEditingController _description;
  late final TextEditingController _notes;

  @override
  void initState() {
    super.initState();
    final item = widget.item;
    _type = item?.type ?? 'placeholder';
    _source = item?.source ?? 'manual';
    _licenseLane = item?.licenseLane ?? 'unknown';
    _query = TextEditingController(text: item?.query ?? '');
    _description = TextEditingController(text: item?.description ?? '');
    _notes = TextEditingController(text: item?.notes ?? '');
  }

  @override
  void dispose() {
    _query.dispose();
    _description.dispose();
    _notes.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          left: 16,
          right: 16,
          top: 16,
          bottom: MediaQuery.of(context).viewInsets.bottom + 16,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                widget.item == null
                    ? 'Adicionar item visual'
                    : 'Editar item visual',
                style: AppTextStyles.cardTitle,
              ),
              const SizedBox(height: 12),
              _OptionRow(
                label: 'Tipo',
                value: _type,
                values: const [
                  'broll',
                  'image',
                  'text_card',
                  'screenshot',
                  'placeholder',
                ],
                onChanged: (value) => setState(() => _type = value),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _query,
                decoration: const InputDecoration(labelText: 'Query'),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _description,
                minLines: 2,
                maxLines: 4,
                decoration: const InputDecoration(labelText: 'Descrição'),
              ),
              const SizedBox(height: 10),
              _OptionRow(
                label: 'Source',
                value: _source,
                values: const [
                  'local',
                  'pexels',
                  'generated',
                  'manual',
                  'placeholder',
                ],
                onChanged: (value) => setState(() => _source = value),
              ),
              const SizedBox(height: 10),
              _OptionRow(
                label: 'Licença',
                value: _licenseLane,
                values: const ['safe', 'review', 'restricted', 'unknown'],
                onChanged: (value) => setState(() => _licenseLane = value),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _notes,
                minLines: 2,
                maxLines: 3,
                decoration: const InputDecoration(labelText: 'Notes'),
              ),
              const SizedBox(height: 14),
              Wrap(
                spacing: 8,
                children: [
                  DFPrimaryButton(
                    label: 'Salvar',
                    icon: Icons.save_rounded,
                    onPressed: () {
                      Navigator.of(context).pop({
                        'type': _type,
                        'query': _query.text,
                        'description': _description.text,
                        'source': _source,
                        'license_lane': _licenseLane,
                        'notes': _notes.text,
                      });
                    },
                  ),
                  DFGhostButton(
                    label: 'Cancelar',
                    icon: Icons.close_rounded,
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StockSearchSheet extends StatefulWidget {
  const _StockSearchSheet({
    required this.initialQuery,
    required this.onSearch,
    required this.onUse,
  });

  final String initialQuery;
  final Future<GenerationStockSearchResponse> Function(String query) onSearch;
  final ValueChanged<GenerationStockMedia> onUse;

  @override
  State<_StockSearchSheet> createState() => _StockSearchSheetState();
}

class _StockSearchSheetState extends State<_StockSearchSheet> {
  late final TextEditingController _query;
  bool _loading = false;
  GenerationStockSearchResponse? _result;

  @override
  void initState() {
    super.initState();
    _query = TextEditingController(text: widget.initialQuery);
  }

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    setState(() => _loading = true);
    final result = await widget.onSearch(_query.text);
    if (!mounted) return;
    setState(() {
      _result = result;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final result = _result;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          left: 16,
          right: 16,
          top: 16,
          bottom: MediaQuery.of(context).viewInsets.bottom + 16,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Buscar stock', style: AppTextStyles.cardTitle),
              const SizedBox(height: 10),
              TextField(
                controller: _query,
                decoration: const InputDecoration(labelText: 'Query'),
                onSubmitted: (_) => _search(),
              ),
              const SizedBox(height: 12),
              DFPrimaryButton(
                label: _loading ? 'Buscando...' : 'Buscar',
                icon: Icons.search_rounded,
                onPressed: _loading ? null : _search,
              ),
              if (result != null) ...[
                const SizedBox(height: 12),
                if (!result.available)
                  const _InlineWarning(
                    message:
                        'Busca de stock não configurada. Use sugestões locais ou adicione manualmente.',
                  )
                else if (result.results.isEmpty)
                  const _InlineWarning(message: 'Nenhum resultado encontrado.')
                else
                  ...result.results.map(
                    (media) => Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: DfCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              media.title.isEmpty
                                  ? media.description
                                  : media.title,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.cardTitle,
                            ),
                            const SizedBox(height: 6),
                            Text(
                              [
                                media.photographer,
                                media.credit,
                              ].where((item) => item.isNotEmpty).join(' · '),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.muted,
                            ),
                            const SizedBox(height: 8),
                            DFSecondaryButton(
                              label: 'Usar',
                              icon: Icons.add_photo_alternate_rounded,
                              onPressed: () => widget.onUse(media),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StepChip extends StatelessWidget {
  const _StepChip({
    required this.label,
    required this.icon,
    required this.status,
    required this.statusKey,
  });

  final String label;
  final IconData icon;
  final String status;
  final String statusKey;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.secondaryBackground,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18, color: AppColors.cyan),
          const SizedBox(width: 6),
          Text(label, style: const TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(width: 8),
          DfStatusChip(label: status, status: statusKey),
        ],
      ),
    );
  }
}

class _OptionRow extends StatelessWidget {
  const _OptionRow({
    required this.label,
    required this.value,
    required this.values,
    required this.onChanged,
  });

  final String label;
  final String value;
  final List<String> values;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return DropdownButtonFormField<String>(
      initialValue: value,
      decoration: InputDecoration(labelText: label),
      items: values.map((item) {
        return DropdownMenuItem(value: item, child: Text(item));
      }).toList(),
      onChanged: (value) {
        if (value != null) onChanged(value);
      },
    );
  }
}

class _DurationRow extends StatelessWidget {
  const _DurationRow({required this.value, required this.onChanged});

  final int value;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<int>(
      segments: const [
        ButtonSegment(value: 60, label: Text('60s')),
        ButtonSegment(value: 90, label: Text('1m30')),
        ButtonSegment(value: 120, label: Text('2m')),
      ],
      selected: {value},
      onSelectionChanged: (values) => onChanged(values.first),
    );
  }
}

class _ScriptDepthRow extends StatelessWidget {
  const _ScriptDepthRow({required this.value, required this.onChanged});

  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<String>(
      segments: const [
        ButtonSegment(value: 'direct', label: Text('Direto')),
        ButtonSegment(value: 'normal', label: Text('Normal')),
        ButtonSegment(value: 'deep', label: Text('Aprofundado')),
      ],
      selected: {value.isEmpty ? 'normal' : value},
      onSelectionChanged: (values) => onChanged(values.first),
    );
  }
}

class _NarrativeStyleRow extends StatelessWidget {
  const _NarrativeStyleRow({required this.value, required this.onChanged});

  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return DropdownButtonFormField<String>(
      initialValue: value.isEmpty ? 'dramatic' : value,
      decoration: const InputDecoration(labelText: 'Estilo narrativo'),
      items: const [
        DropdownMenuItem(value: 'documentary', child: Text('Documentário')),
        DropdownMenuItem(value: 'emotional', child: Text('Emocional')),
        DropdownMenuItem(value: 'mystery', child: Text('Mistério')),
        DropdownMenuItem(value: 'controversial', child: Text('Polêmico')),
        DropdownMenuItem(value: 'explanatory', child: Text('Explicativo')),
        DropdownMenuItem(value: 'dramatic', child: Text('Dramático')),
      ],
      onChanged: (value) {
        if (value != null) onChanged(value);
      },
    );
  }
}

class _EmptyCard extends StatelessWidget {
  const _EmptyCard({required this.title, required this.text});

  final String title;
  final String text;

  @override
  Widget build(BuildContext context) {
    return DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: AppTextStyles.cardTitle),
          const SizedBox(height: 6),
          Text(text, style: const TextStyle(color: AppColors.secondaryText)),
        ],
      ),
    );
  }
}

class _InlineError extends StatelessWidget {
  const _InlineError({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return DfCard(
      color: AppColors.danger.withValues(alpha: 0.08),
      child: Text(message, style: const TextStyle(color: AppColors.danger)),
    );
  }
}

class _InlineWarning extends StatelessWidget {
  const _InlineWarning({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.warning.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.warning.withValues(alpha: 0.22)),
      ),
      child: Text(
        message,
        maxLines: 3,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(color: AppColors.warning),
      ),
    );
  }
}

String _rateForSpeed(String speed) {
  return switch (speed) {
    'Lenta' => '-12%',
    'Rápida' => '+14%',
    _ => '+0%',
  };
}

String _voiceStatusLabel(String status) {
  return switch (status) {
    'ready' => 'Narração pronta',
    'failed' => 'Falha ao gerar narração',
    'generating' => 'Gerando narração...',
    _ => 'Sem narração',
  };
}

String _visualStatusLabel(String status) {
  return switch (status) {
    'draft' => 'Visual em rascunho',
    'ready' => 'Visual pronto',
    'failed' => 'Visual com falha',
    _ => 'Sem visual',
  };
}

String _licenseLabel(String lane) {
  return switch (lane) {
    'safe' => 'Seguro',
    'review' => 'Revisar',
    'restricted' => 'Restrito',
    _ => 'Desconhecido',
  };
}

String _licenseStatus(String lane) {
  return switch (lane) {
    'safe' => 'success',
    'review' => 'warning',
    'restricted' => 'failed',
    _ => '',
  };
}

String _visualItemStatus(String status) {
  return switch (status) {
    'selected' => 'success',
    'ready' => 'success',
    'rejected' => 'failed',
    'missing' => 'warning',
    _ => '',
  };
}

String _qualityStatus(String tier) {
  return switch (tier) {
    'excellent' => 'success',
    'good' => 'success',
    'average' => 'warning',
    'weak' => 'warning',
    'reject' => 'failed',
    _ => '',
  };
}

String _durationLabel(int value) {
  return switch (value) {
    90 => '1m30',
    120 => '2m',
    _ => '60s',
  };
}

String _depthLabel(String value) {
  return switch (value) {
    'direct' => 'Direto',
    'deep' => 'Aprofundado',
    _ => 'Normal',
  };
}

String _styleLabel(String value) {
  return switch (value) {
    'documentary' => 'Documentário',
    'emotional' => 'Emocional',
    'mystery' => 'Mistério/curiosidade',
    'controversial' => 'Polêmico',
    'explanatory' => 'Explicativo',
    _ => 'Dramático',
  };
}

String _field(Map<String, dynamic> map, String key) {
  return map[key]?.toString().trim() ?? '';
}

String _scriptLineFor(GenerationProject project, GenerationVisualItem item) {
  final index = item.scriptLineIndex;
  if (index >= 0 && index < project.scriptLines.length) {
    return project.scriptLines[index];
  }
  return item.description;
}

List<String> _lines(String value) {
  return value
      .split('\n')
      .map((line) => line.trim())
      .where((line) => line.isNotEmpty)
      .toList();
}
