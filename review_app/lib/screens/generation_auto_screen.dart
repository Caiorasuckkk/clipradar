import 'dart:async';

import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import '../widgets/clip_video_player.dart';
import '../widgets/df_button.dart';
import '../widgets/df_card.dart';
import '../widgets/df_section_header.dart';

/// One-shot generation for the Histórico & Curiosidades studio: see what's
/// trending, pick a theme, choose languages (pt-BR and/or en-US), and one tap
/// generates a full video per language to feed two channels at once.
class GenerationAutoScreen extends StatefulWidget {
  const GenerationAutoScreen({
    super.key,
    this.personaId = 'historico',
    this.personaLabel = 'Histórico & Curiosidades',
    this.personaVoice = '',
  });

  final String personaId;
  final String personaLabel;
  final String personaVoice;

  @override
  State<GenerationAutoScreen> createState() => _GenerationAutoScreenState();
}

class _GenerationAutoScreenState extends State<GenerationAutoScreen> {
  final ApiClient _api = ApiClient();
  final TextEditingController _theme = TextEditingController();

  String _speed = 'normal';
  String _voice = '';
  final Set<String> _languages = {'pt-BR', 'en-US'};

  List<GenerationTrend>? _trends;
  bool _trendsLoading = false;
  String? _trendsError;

  bool _starting = false;
  String? _error;
  final List<_AutoJob> _jobs = [];
  Timer? _poll;
  bool _polling = false;

  static const _langOptions = {
    'pt-BR': 'Português',
    'en-US': 'Inglês',
  };
  static const _speeds = {
    'lento': 'Lenta',
    'normal': 'Normal',
    'rapido': 'Rápida',
  };
  static const _voices = {
    '': 'Padrão do estúdio (Onyx)',
    'openai:onyx': 'Onyx (grave)',
    'openai:fable': 'Fable (narrador)',
    'openai:nova': 'Nova (feminina)',
    'openai:echo': 'Echo (masculina)',
    'pt-BR-ThalitaMultilingualNeural': 'Thalita (grátis)',
    'elevenlabs:onwK4e9ZLuTAKqWW03F9': 'Daniel (ElevenLabs)',
    'elevenlabs:pNInz6obpgDQGcFmaJgB': 'Adam (ElevenLabs)',
    'elevenlabs:EXAVITQu4vr4xnSDxMaL': 'Sarah (ElevenLabs)',
  };
  static const _statusLabels = {
    'queued': 'Na fila...',
    'scripting': 'Escrevendo o roteiro...',
    'visuals': 'Escolhendo as imagens...',
    'voice': 'Gerando a narração...',
    'rendering': 'Renderizando o vídeo...',
    'ready': 'Vídeo pronto!',
    'failed': 'Falhou',
    'cancelled': 'Cancelado',
  };

  @override
  void initState() {
    super.initState();
    if (_voices.containsKey(widget.personaVoice)) _voice = widget.personaVoice;
    _loadTrends();
  }

  @override
  void dispose() {
    _poll?.cancel();
    _theme.dispose();
    super.dispose();
  }

  bool get _running =>
      _jobs.isNotEmpty &&
      _jobs.any((j) => j.status == null || !j.status!.isTerminal);
  bool get _busy => _starting || _running;

  Future<void> _loadTrends({bool refresh = false}) async {
    setState(() {
      _trendsLoading = true;
      _trendsError = null;
    });
    try {
      final trends = await _api.fetchTrendingTopics(refresh: refresh);
      if (!mounted) return;
      setState(() {
        _trends = trends;
        _trendsLoading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _trendsError = error.toString();
        _trendsLoading = false;
      });
    }
  }

  Future<void> _generate() async {
    final theme = _theme.text.trim();
    if (theme.isEmpty) {
      setState(() => _error = 'Escreva (ou escolha) um tema para gerar.');
      return;
    }
    if (_languages.isEmpty) {
      setState(() => _error = 'Selecione pelo menos um idioma.');
      return;
    }
    setState(() {
      _starting = true;
      _error = null;
      _jobs.clear();
    });
    // Generate pt-BR before en-US so the first channel starts sooner.
    final langs = _langOptions.keys.where(_languages.contains).toList();
    try {
      final items = await _api.startAutoGenerationBatch(
        theme: theme,
        persona: widget.personaId,
        speed: _speed,
        voice: _voice,
        languages: langs,
      );
      if (!mounted) return;
      setState(() {
        _starting = false;
        for (final item in items) {
          if (item.ok) {
            _jobs.add(_AutoJob(language: item.language, projectId: item.projectId));
          }
        }
        if (_jobs.isEmpty) {
          _error = 'Não foi possível iniciar a geração.';
        }
      });
      if (_jobs.isNotEmpty) _startPolling();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _starting = false;
      });
    }
  }

  void _startPolling() {
    _poll?.cancel();
    _poll = Timer.periodic(const Duration(seconds: 3), (_) => _tick());
    _tick();
  }

  Future<void> _tick() async {
    if (_polling) return;
    _polling = true;
    try {
      await Future.wait(_jobs
          .where((j) => j.status == null || !j.status!.isTerminal)
          .map((j) async {
        try {
          final status = await _api.fetchAutoStatus(j.projectId);
          j.status = status;
        } catch (_) {
          // Transient polling errors are ignored; the next tick retries.
        }
      }));
      if (!mounted) return;
      setState(() {});
      if (!_running) _poll?.cancel();
    } finally {
      _polling = false;
    }
  }

  void _reset() {
    _poll?.cancel();
    setState(() {
      _jobs.clear();
      _error = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.personaLabel)),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(18),
          children: [
            const DfSectionHeader(
              title: 'Histórico & Curiosidades',
              subtitle:
                  'Veja o que está em alta, escolha um tema e gere em português e inglês de uma vez.',
            ),
            _trendingCard(),
            const SizedBox(height: 16),
            _composerCard(),
            for (final job in _jobs) ...[
              const SizedBox(height: 16),
              _ProgressCard(
                heading: _langOptions[job.language] ?? job.language,
                status: job.status,
                label: _statusLabels[job.status?.status ?? 'queued'] ??
                    'Processando...',
                videoUrl: _api.generationRenderVideoUrl(job.projectId),
              ),
            ],
            if (_jobs.isNotEmpty && !_running) ...[
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: DFSecondaryButton(
                  label: 'Gerar outros vídeos',
                  icon: Icons.refresh_rounded,
                  onPressed: _reset,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _trendingCard() {
    return DfCard(
      color: AppColors.surfaceAlt,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.local_fire_department_rounded,
                  color: AppColors.warning, size: 20),
              const SizedBox(width: 6),
              const Expanded(
                child: Text('Em alta agora', style: AppTextStyles.cardTitle),
              ),
              IconButton(
                tooltip: 'Atualizar tendências',
                visualDensity: VisualDensity.compact,
                onPressed: _trendsLoading ? null : () => _loadTrends(refresh: true),
                icon: _trendsLoading
                    ? const SizedBox.square(
                        dimension: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.refresh_rounded, size: 18),
              ),
            ],
          ),
          const Text(
            'Top temas mais buscados/vistos no YouTube e TikTok. Toque para usar.',
            style: AppTextStyles.muted,
          ),
          const SizedBox(height: 10),
          _trendingBody(),
        ],
      ),
    );
  }

  Widget _trendingBody() {
    if (_trendsLoading && _trends == null) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 16),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (_trendsError != null && _trends == null) {
      return Row(
        children: [
          const Expanded(
            child: Text('Não foi possível carregar as tendências.',
                style: TextStyle(color: AppColors.danger)),
          ),
          TextButton(onPressed: () => _loadTrends(refresh: true), child: const Text('Tentar')),
        ],
      );
    }
    final trends = _trends ?? [];
    if (trends.isEmpty) {
      return const Text('Sem sugestões no momento.', style: AppTextStyles.muted);
    }
    return Column(
      children: [
        for (var i = 0; i < trends.length; i++)
          _TrendTile(
            index: i + 1,
            trend: trends[i],
            disabled: _busy,
            onTap: () {
              _theme.text = trends[i].title;
              setState(() => _error = null);
            },
          ),
      ],
    );
  }

  Widget _composerCard() {
    return DfCard(
      color: AppColors.surfaceAlt,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Tema do vídeo', style: AppTextStyles.cardTitle),
          const SizedBox(height: 8),
          TextField(
            controller: _theme,
            enabled: !_busy,
            minLines: 2,
            maxLines: 4,
            textInputAction: TextInputAction.newline,
            decoration: const InputDecoration(
              hintText: 'Ex: O imperador romano que nomeou seu cavalo senador',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          const Text('Idiomas (1 vídeo por idioma)', style: AppTextStyles.muted),
          const SizedBox(height: 6),
          Wrap(
            spacing: 8,
            children: [
              for (final entry in _langOptions.entries)
                FilterChip(
                  label: Text(entry.value),
                  selected: _languages.contains(entry.key),
                  onSelected: _busy
                      ? null
                      : (sel) => setState(() {
                            if (sel) {
                              _languages.add(entry.key);
                            } else if (_languages.length > 1) {
                              _languages.remove(entry.key);
                            }
                          }),
                ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _Dropdown(
                  label: 'Velocidade da fala',
                  value: _speed,
                  items: _speeds,
                  enabled: !_busy,
                  onChanged: (v) => setState(() => _speed = v),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _Dropdown(
                  label: 'Voz do narrador',
                  value: _voice,
                  items: _voices,
                  enabled: !_busy,
                  onChanged: (v) => setState(() => _voice = v),
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          SizedBox(
            width: double.infinity,
            child: DFPrimaryButton(
              label: _busy
                  ? 'Gerando...'
                  : 'Gerar ${_languages.length} vídeo${_languages.length > 1 ? 's' : ''}',
              icon: Icons.auto_awesome_rounded,
              onPressed: _busy ? null : _generate,
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: AppColors.danger)),
          ],
        ],
      ),
    );
  }
}

class _AutoJob {
  _AutoJob({required this.language, required this.projectId});

  final String language;
  final String projectId;
  GenerationAutoStatus? status;
}

class _TrendTile extends StatelessWidget {
  const _TrendTile({
    required this.index,
    required this.trend,
    required this.onTap,
    required this.disabled,
  });

  final int index;
  final GenerationTrend trend;
  final VoidCallback onTap;
  final bool disabled;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: disabled ? null : onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 24,
              height: 24,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppColors.warning.withValues(alpha: 0.16),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text('$index',
                  style: const TextStyle(
                      color: AppColors.warning,
                      fontWeight: FontWeight.w800,
                      fontSize: 12)),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(trend.title,
                      style: const TextStyle(fontWeight: FontWeight.w700)),
                  if (trend.why.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Text(trend.why, style: AppTextStyles.muted),
                  ],
                ],
              ),
            ),
            const Icon(Icons.north_west_rounded,
                size: 16, color: AppColors.secondaryText),
          ],
        ),
      ),
    );
  }
}

class _Dropdown extends StatelessWidget {
  const _Dropdown({
    required this.label,
    required this.value,
    required this.items,
    required this.onChanged,
    required this.enabled,
  });

  final String label;
  final String value;
  final Map<String, String> items;
  final ValueChanged<String> onChanged;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    return DropdownButtonFormField<String>(
      initialValue: value,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      ),
      isExpanded: true,
      items: items.entries
          .map((e) => DropdownMenuItem(value: e.key, child: Text(e.value)))
          .toList(),
      onChanged: enabled ? (v) => v != null ? onChanged(v) : null : null,
    );
  }
}

class _ProgressCard extends StatelessWidget {
  const _ProgressCard({
    required this.heading,
    required this.status,
    required this.label,
    required this.videoUrl,
  });

  final String heading;
  final GenerationAutoStatus? status;
  final String label;
  final String videoUrl;

  @override
  Widget build(BuildContext context) {
    final s = status;
    final isReady = s?.status == 'ready';
    final isFailed = s?.status == 'failed' || s?.status == 'cancelled';
    final progress = s?.progress ?? 0.0;

    return DfCard(
      color: AppColors.surfaceAlt,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                isReady
                    ? Icons.check_circle_rounded
                    : isFailed
                        ? Icons.error_rounded
                        : Icons.autorenew_rounded,
                color: isReady
                    ? AppColors.success
                    : isFailed
                        ? AppColors.danger
                        : AppColors.cyan,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text('$heading · $label',
                    style: AppTextStyles.cardTitle),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (!isReady && !isFailed)
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: progress > 0 ? progress : null,
                minHeight: 8,
                backgroundColor: AppColors.border,
              ),
            ),
          if ((s?.degraded ?? false) && (s?.warning ?? '').isNotEmpty) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.warning.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.warning_amber_rounded,
                      color: AppColors.warning, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(s!.warning,
                        style: const TextStyle(color: AppColors.warning)),
                  ),
                ],
              ),
            ),
          ],
          if (isFailed && (s?.error ?? '').isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(s!.error, style: const TextStyle(color: AppColors.danger)),
          ],
          if (isReady) ...[
            const SizedBox(height: 12),
            ClipVideoPlayer(url: videoUrl, aspectRatio: 9 / 16),
            if (s?.scriptQualityScore != null) ...[
              const SizedBox(height: 10),
              Text(
                'Qualidade do roteiro: ${s!.scriptQualityScore!.toStringAsFixed(1)} (${s.scriptQualityTier})',
                style: AppTextStyles.muted,
              ),
            ],
          ],
        ],
      ),
    );
  }
}
