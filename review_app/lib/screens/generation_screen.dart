import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:audioplayers/audioplayers.dart';

import '../core/api_client.dart';
import '../models/generation_project.dart';
import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import '../widgets/df_button.dart';
import '../widgets/df_card.dart';
import '../widgets/df_page_scaffold.dart';
import '../widgets/df_section_header.dart';
import '../widgets/df_status_chip.dart';

enum _GenerationTab { ideas, script, voice, projects }

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

  _GenerationTab _tab = _GenerationTab.ideas;
  String _tone = 'curioso';
  String _language = 'pt-BR';
  int _duration = 45;
  bool _loadingIdeas = false;
  bool _loadingScript = false;
  bool _loadingProjects = true;
  bool _loadingVoices = true;
  bool _savingProject = false;
  bool _generatingVoice = false;
  bool _playingVoice = false;
  String? _error;
  GenerationIdea? _selectedIdea;
  GenerationScript? _script;
  GenerationProject? _selectedProject;
  GenerationVoicesResponse? _voicesResponse;
  String _selectedVoice = 'pt-BR-AntonioNeural';
  String _voiceSpeed = 'Normal';
  List<GenerationIdea> _ideas = const [];
  List<GenerationProject> _projects = const [];

  @override
  void initState() {
    super.initState();
    _loadProjects();
    _loadVoices();
    _audioPlayer.onPlayerComplete.listen((_) {
      if (mounted) setState(() => _playingVoice = false);
    });
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

  void _openProject(GenerationProject project) {
    final script = GenerationScript(
      title: project.title,
      hook: project.hook,
      scriptLines: project.scriptLines,
      cta: project.cta,
      hashtags: project.hashtags,
      visualContext: project.visualContext,
      niche: project.niche,
      language: project.language,
      tone: project.tone,
      status: project.status,
    );
    _applyScript(script);
    setState(() {
      _script = script;
      _selectedProject = project;
      _selectedIdea = null;
      _tab = _GenerationTab.script;
    });
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
        const _PipelineStatus(),
        const SizedBox(height: 14),
        SegmentedButton<_GenerationTab>(
          segments: const [
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
              value: _GenerationTab.projects,
              icon: Icon(Icons.folder_copy_rounded),
              label: Text('Projetos'),
            ),
          ],
          selected: {_tab},
          onSelectionChanged: (value) => setState(() => _tab = value.first),
        ),
        const SizedBox(height: 14),
        switch (_tab) {
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
          _GenerationTab.projects => _ProjectsSection(
            loading: _loadingProjects,
            projects: _projects,
            onRefresh: _loadProjects,
            onOpen: _openProject,
            onArchive: _archiveProject,
            onDelete: _deleteProject,
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
                  'Voz, Visual/B-roll e Render continuam em preparação. Para produção pronta agora, use Cortes.',
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

class _PipelineStatus extends StatelessWidget {
  const _PipelineStatus();

  @override
  Widget build(BuildContext context) {
    final steps = [
      ('Ideias', Icons.lightbulb_rounded, 'Ativo', 'success'),
      ('Roteiro', Icons.edit_note_rounded, 'Ativo', 'success'),
      ('Voz', Icons.graphic_eq_rounded, 'Ativo', 'success'),
      ('Visual/B-roll', Icons.video_library_rounded, 'Em breve', ''),
      ('Render', Icons.smart_display_rounded, 'Em breve', ''),
    ];
    return DfCard(
      color: AppColors.surfaceAlt,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Pipeline de Geração', style: AppTextStyles.cardTitle),
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
                subtitle: 'Gere ângulos locais com templates, sem IA externa.',
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
    required this.script,
    required this.titleController,
    required this.hookController,
    required this.scriptController,
    required this.ctaController,
    required this.hashtagsController,
    required this.visualController,
    required this.onSave,
    required this.onCopy,
  });

  final bool loading;
  final bool saving;
  final GenerationScript? script;
  final TextEditingController titleController;
  final TextEditingController hookController;
  final TextEditingController scriptController;
  final TextEditingController ctaController;
  final TextEditingController hashtagsController;
  final TextEditingController visualController;
  final VoidCallback onSave;
  final VoidCallback onCopy;

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
            ],
          ),
        ],
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
  });

  final bool loading;
  final List<GenerationProject> projects;
  final VoidCallback onRefresh;
  final ValueChanged<GenerationProject> onOpen;
  final ValueChanged<GenerationProject> onArchive;
  final ValueChanged<GenerationProject> onDelete;

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
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: idea.suggestedHashtags
                  .take(4)
                  .map((tag) => DfStatusChip(label: tag))
                  .toList(),
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
  });

  final GenerationProject project;
  final ValueChanged<GenerationProject> onOpen;
  final ValueChanged<GenerationProject> onArchive;
  final ValueChanged<GenerationProject> onDelete;

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
        ButtonSegment(value: 30, label: Text('30s')),
        ButtonSegment(value: 45, label: Text('45s')),
        ButtonSegment(value: 60, label: Text('60s')),
      ],
      selected: {value},
      onSelectionChanged: (values) => onChanged(values.first),
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

List<String> _lines(String value) {
  return value
      .split('\n')
      .map((line) => line.trim())
      .where((line) => line.isNotEmpty)
      .toList();
}
