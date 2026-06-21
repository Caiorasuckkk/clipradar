import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api_client.dart';
import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import '../widgets/clip_video_player.dart';
import '../widgets/df_button.dart';
import '../widgets/df_card.dart';

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

  final Map<String, PublishPack> _packs = {}; // pacote de publicação por idioma
  String? _publishLang; // idioma selecionado no card "Pronto pra postar"
  final Set<String> _regenLangs = {}; // idiomas com pacote sendo regerado

  List<GenerationPersona>? _personas;
  GenerationPersona? _persona;
  bool _personasLoading = true;

  Color get _accent => _accentColor(_persona?.accent);
  String get _personaId => _persona?.id ?? widget.personaId;
  String get _personaLabel => _persona?.label ?? widget.personaLabel;
  String get _personaDescription =>
      _persona?.description ?? 'Tema → vídeo narrado, em PT e EN.';

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
    '': 'Voz padrão do estúdio',
    'xtts:marco': 'Marco (sua voz, local)',
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
    _loadPersonas();
    _loadTrends();
  }

  Future<void> _loadPersonas() async {
    try {
      final personas = await _api.fetchGenerationPersonas();
      if (!mounted) return;
      GenerationPersona? selected;
      for (final p in personas) {
        if (p.id == widget.personaId) {
          selected = p;
          break;
        }
      }
      selected ??= personas.isNotEmpty ? personas.first : null;
      setState(() {
        _personas = personas;
        _persona = selected;
        _personasLoading = false;
      });
      _loadTrends(); // refresh trends for the resolved studio's niche
    } catch (_) {
      // Studio selection is optional; fall back to the persona passed in.
      if (!mounted) return;
      setState(() => _personasLoading = false);
    }
  }

  void _selectPersona(GenerationPersona persona) {
    if (_busy || persona.id == _persona?.id) return;
    setState(() {
      _persona = persona;
      _voice = ''; // back to the studio's default voice
      _error = null;
    });
    _loadTrends(); // pull trending topics for the new studio's niche
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
      final niche = _persona?.niche ?? '';
      final trends = await _api.fetchTrendingTopics(
        niche: niche.isNotEmpty ? niche : 'história e curiosidades',
        refresh: refresh,
      );
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
    final langs = _langOptions.keys.where(_languages.contains).toList();
    try {
      final items = await _api.startAutoGenerationBatch(
        theme: theme,
        persona: _personaId,
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
      // Fetch the publish pack for each newly-ready job (in its language).
      await Future.wait(_jobs
          .where((j) => j.status?.status == 'ready' && !_packs.containsKey(j.language))
          .map((j) async {
        try {
          _packs[j.language] = await _api.fetchGenerationPublishPack(j.projectId);
          _publishLang ??= j.language;
        } catch (_) {
          // Pack is best-effort; the next tick retries.
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
      _packs.clear();
      _publishLang = null;
      _error = null;
    });
  }

  void _copy(String text, String label) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$label copiado'), duration: const Duration(seconds: 1)),
    );
  }

  Future<void> _regeneratePack(String lang) async {
    final idx = _jobs.indexWhere((j) => j.language == lang);
    if (idx < 0 || _regenLangs.contains(lang)) return;
    setState(() => _regenLangs.add(lang));
    try {
      final pack =
          await _api.fetchGenerationPublishPack(_jobs[idx].projectId, refresh: true);
      if (!mounted) return;
      setState(() => _packs[lang] = pack);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Não foi possível regerar o pacote.')),
        );
      }
    } finally {
      if (mounted) setState(() => _regenLangs.remove(lang));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        scrolledUnderElevation: 0,
        title: const Text('Criar vídeo'),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
          children: [
            _hero(),
            const SizedBox(height: 24),
            _studioSection(),
            const SizedBox(height: 24),
            _trendingSection(),
            const SizedBox(height: 24),
            _composer(),
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
            if (_packs.isNotEmpty) ...[
              const SizedBox(height: 20),
              _publishSection(),
            ],
            if (_jobs.isNotEmpty && !_running) ...[
              const SizedBox(height: 20),
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

  // --- Hero --------------------------------------------------------------
  Widget _hero() {
    return Row(
      children: [
        Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: _accent.withValues(alpha: 0.14),
            borderRadius: BorderRadius.circular(14),
          ),
          child: Icon(_personaIcon(_persona?.icon), color: _accent),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(_personaLabel, style: AppTextStyles.title),
              const SizedBox(height: 2),
              Text(
                _personaDescription,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.muted,
              ),
            ],
          ),
        ),
      ],
    );
  }

  // --- Studio selector ---------------------------------------------------
  Widget _studioSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _label('ESTÚDIO'),
        const SizedBox(height: 4),
        const Text(
          'Cada estúdio ajusta roteiro, voz e visual do canal.',
          style: AppTextStyles.muted,
        ),
        const SizedBox(height: 12),
        _studioBody(),
      ],
    );
  }

  Widget _studioBody() {
    if (_personasLoading) {
      return const SizedBox(
        height: 96,
        child: Center(
          child: SizedBox.square(
            dimension: 22,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        ),
      );
    }
    final personas = _personas ?? const [];
    if (personas.isEmpty) {
      return const Text(
        'Nenhum estúdio disponível no momento.',
        style: AppTextStyles.muted,
      );
    }
    return SizedBox(
      height: 124,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: personas.length,
        separatorBuilder: (_, _) => const SizedBox(width: 12),
        itemBuilder: (context, i) {
          final p = personas[i];
          return _StudioCard(
            label: p.label,
            icon: _personaIcon(p.icon),
            accent: _accentColor(p.accent),
            selected: p.id == _persona?.id,
            disabled: _busy,
            onTap: () => _selectPersona(p),
          );
        },
      ),
    );
  }

  // --- Trending ----------------------------------------------------------
  Widget _trendingSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.local_fire_department_rounded,
                color: AppColors.warning, size: 18),
            const SizedBox(width: 8),
            Expanded(child: _label('EM ALTA AGORA')),
            _iconAction(
              loading: _trendsLoading,
              icon: Icons.refresh_rounded,
              onTap: _trendsLoading ? null : () => _loadTrends(refresh: true),
            ),
          ],
        ),
        const SizedBox(height: 4),
        const Text('Toque em um tema para usá-lo.', style: AppTextStyles.muted),
        const SizedBox(height: 12),
        DfCard(
          color: AppColors.surfaceAlt,
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
          child: _trendingBody(),
        ),
      ],
    );
  }

  Widget _trendingBody() {
    if (_trendsLoading && _trends == null) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 28),
        child: Center(
          child: SizedBox.square(
            dimension: 22,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        ),
      );
    }
    if (_trendsError != null && _trends == null) {
      return Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            const Expanded(
              child: Text('Não foi possível carregar as tendências.',
                  style: TextStyle(color: AppColors.danger)),
            ),
            TextButton(
                onPressed: () => _loadTrends(refresh: true),
                child: const Text('Tentar')),
          ],
        ),
      );
    }
    final trends = _trends ?? [];
    if (trends.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Text('Sem sugestões no momento.', style: AppTextStyles.muted),
      );
    }
    return Column(
      children: [
        for (var i = 0; i < trends.length; i++) ...[
          if (i > 0)
            const Divider(height: 1, thickness: 1, color: AppColors.border, indent: 12, endIndent: 12),
          _TrendTile(
            index: i + 1,
            trend: trends[i],
            disabled: _busy,
            accent: _accent,
            onTap: () {
              _theme.text = trends[i].title;
              setState(() => _error = null);
            },
          ),
        ],
      ],
    );
  }

  // --- Composer ----------------------------------------------------------
  Widget _composer() {
    final count = _languages.length;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _label('TEMA DO VÍDEO'),
        const SizedBox(height: 10),
        TextField(
          controller: _theme,
          enabled: !_busy,
          minLines: 2,
          maxLines: 4,
          style: AppTextStyles.body,
          textInputAction: TextInputAction.newline,
          decoration: _fieldDecoration(
            'Ex: O imperador romano que nomeou seu cavalo senador',
          ),
        ),
        const SizedBox(height: 20),
        _label('IDIOMAS'),
        const SizedBox(height: 4),
        const Text('Um vídeo por idioma (2 canais).', style: AppTextStyles.muted),
        const SizedBox(height: 10),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: [
            for (final entry in _langOptions.entries)
              _langChip(entry.key, entry.value),
          ],
        ),
        const SizedBox(height: 20),
        Row(
          children: [
            Expanded(
              child: _Dropdown(
                label: 'Velocidade',
                value: _speed,
                items: _speeds,
                enabled: !_busy,
                onChanged: (v) => setState(() => _speed = v),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _Dropdown(
                label: 'Voz',
                value: _voice,
                items: _voices,
                enabled: !_busy,
                onChanged: (v) => setState(() => _voice = v),
              ),
            ),
          ],
        ),
        const SizedBox(height: 22),
        SizedBox(
          width: double.infinity,
          height: 54,
          child: DFPrimaryButton(
            label: _busy ? 'Gerando...' : 'Gerar $count vídeo${count > 1 ? 's' : ''}',
            icon: Icons.auto_awesome_rounded,
            onPressed: _busy ? null : _generate,
          ),
        ),
        if (_error != null) ...[
          const SizedBox(height: 12),
          Row(
            children: [
              const Icon(Icons.error_outline_rounded, color: AppColors.danger, size: 18),
              const SizedBox(width: 8),
              Expanded(
                child: Text(_error!, style: const TextStyle(color: AppColors.danger)),
              ),
            ],
          ),
        ],
      ],
    );
  }

  Widget _langChip(String key, String text) {
    final selected = _languages.contains(key);
    return FilterChip(
      label: Text(text),
      selected: selected,
      showCheckmark: false,
      backgroundColor: AppColors.surfaceAlt,
      selectedColor: _accent.withValues(alpha: 0.16),
      side: BorderSide(color: selected ? _accent : AppColors.border),
      labelStyle: TextStyle(
        color: selected ? _accent : AppColors.secondaryText,
        fontWeight: FontWeight.w700,
      ),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      onSelected: _busy
          ? null
          : (sel) => setState(() {
                if (sel) {
                  _languages.add(key);
                } else if (_languages.length > 1) {
                  _languages.remove(key);
                }
              }),
    );
  }

  // --- Shared bits -------------------------------------------------------
  // --- Publish pack ------------------------------------------------------
  Widget _publishSection() {
    final langs = _packs.keys.toList();
    final lang = (_publishLang != null && _packs.containsKey(_publishLang))
        ? _publishLang!
        : (langs.isNotEmpty ? langs.first : '');
    final pack = _packs[lang];
    if (pack == null) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.ios_share_rounded, color: AppColors.success, size: 18),
            const SizedBox(width: 8),
            Expanded(child: _label('PRONTO PRA POSTAR')),
            TextButton.icon(
              onPressed: _regenLangs.contains(lang) ? null : () => _regeneratePack(lang),
              icon: _regenLangs.contains(lang)
                  ? const SizedBox.square(
                      dimension: 14, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.refresh_rounded, size: 16),
              label: const Text('Regerar'),
            ),
          ],
        ),
        const SizedBox(height: 4),
        const Text('Copie e cole no YouTube / TikTok / Reels.', style: AppTextStyles.muted),
        if (langs.length > 1) ...[
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            children: [
              for (final l in langs)
                ChoiceChip(
                  label: Text(_langOptions[l] ?? l),
                  selected: l == lang,
                  showCheckmark: false,
                  backgroundColor: AppColors.surfaceAlt,
                  selectedColor: _accent.withValues(alpha: 0.16),
                  side: BorderSide(color: l == lang ? _accent : AppColors.border),
                  labelStyle: TextStyle(
                    color: l == lang ? _accent : AppColors.secondaryText,
                    fontWeight: FontWeight.w700,
                  ),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  onSelected: (_) => setState(() => _publishLang = l),
                ),
            ],
          ),
        ],
        const SizedBox(height: 12),
        DfCard(
          color: AppColors.surfaceAlt,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _label('TÍTULOS (escolha 1)'),
              const SizedBox(height: 4),
              for (final t in pack.titles) _copyRow(t, 'Título'),
              if (pack.description.isNotEmpty) ...[
                const Divider(height: 24, thickness: 1, color: AppColors.border),
                _label('DESCRIÇÃO'),
                const SizedBox(height: 4),
                _copyRow(pack.description, 'Descrição', maxLines: 5),
              ],
              if (pack.hashtags.isNotEmpty) ...[
                const Divider(height: 24, thickness: 1, color: AppColors.border),
                _label('HASHTAGS'),
                const SizedBox(height: 4),
                _copyRow(pack.hashtags.join(' '), 'Hashtags', maxLines: 4),
              ],
              if (pack.bestTimes.isNotEmpty) ...[
                const Divider(height: 24, thickness: 1, color: AppColors.border),
                _label('MELHORES HORÁRIOS'),
                const SizedBox(height: 6),
                Text(pack.bestTimes, style: AppTextStyles.muted),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _copyRow(String text, String label, {int maxLines = 2}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Text(text,
                maxLines: maxLines,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.body),
          ),
          const SizedBox(width: 6),
          InkWell(
            onTap: () => _copy(text, label),
            borderRadius: BorderRadius.circular(8),
            child: const Padding(
              padding: EdgeInsets.all(4),
              child: Icon(Icons.copy_rounded, size: 16, color: AppColors.secondaryText),
            ),
          ),
        ],
      ),
    );
  }

  Widget _label(String text) {
    return Text(text, style: AppTextStyles.label);
  }

  Widget _iconAction({required IconData icon, required bool loading, VoidCallback? onTap}) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Padding(
        padding: const EdgeInsets.all(6),
        child: loading
            ? const SizedBox.square(
                dimension: 16, child: CircularProgressIndicator(strokeWidth: 2))
            : Icon(icon, size: 18, color: AppColors.secondaryText),
      ),
    );
  }

  InputDecoration _fieldDecoration(String hint) {
    OutlineInputBorder border(Color c) => OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: c),
        );
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: AppColors.muted),
      filled: true,
      fillColor: AppColors.surfaceAlt,
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      enabledBorder: border(AppColors.border),
      focusedBorder: border(_accent),
      disabledBorder: border(AppColors.border),
    );
  }
}

IconData _personaIcon(String? name) {
  switch (name) {
    case 'rocket_launch':
      return Icons.rocket_launch_rounded;
    case 'auto_awesome':
      return Icons.auto_awesome_rounded;
    case 'auto_stories':
      return Icons.auto_stories_rounded;
    case 'psychology':
      return Icons.psychology_rounded;
    case 'dark_mode':
      return Icons.dark_mode_rounded;
    default:
      return Icons.movie_filter_rounded;
  }
}

Color _accentColor(String? name) {
  switch (name) {
    case 'warning':
      return AppColors.warning;
    case 'purple':
      return AppColors.purple;
    case 'blue':
      return AppColors.blue;
    case 'success':
      return AppColors.success;
    case 'danger':
      return AppColors.danger;
    case 'cyan':
    default:
      return AppColors.cyan;
  }
}

class _StudioCard extends StatelessWidget {
  const _StudioCard({
    required this.label,
    required this.icon,
    required this.accent,
    required this.selected,
    required this.disabled,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final Color accent;
  final bool selected;
  final bool disabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: disabled && !selected ? 0.5 : 1,
      child: InkWell(
        onTap: disabled ? null : onTap,
        borderRadius: BorderRadius.circular(16),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          width: 132,
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: selected
                ? accent.withValues(alpha: 0.12)
                : AppColors.surfaceAlt,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: selected ? accent : AppColors.border,
              width: selected ? 1.5 : 1,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: accent, size: 22),
              ),
              const SizedBox(height: 10),
              Flexible(
                child: Text(
                  label,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: selected ? AppColors.text : AppColors.secondaryText,
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    height: 1.2,
                  ),
                ),
              ),
            ],
          ),
        ),
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
    required this.accent,
  });

  final int index;
  final GenerationTrend trend;
  final VoidCallback onTap;
  final bool disabled;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: disabled ? null : onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Container(
              width: 26,
              height: 26,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: accent.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text('$index',
                  style: TextStyle(
                      color: accent, fontWeight: FontWeight.w800, fontSize: 12)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(trend.title,
                      style: const TextStyle(
                          color: AppColors.text,
                          fontWeight: FontWeight.w600,
                          height: 1.25)),
                  if (trend.why.isNotEmpty) ...[
                    const SizedBox(height: 3),
                    Text(trend.why, style: AppTextStyles.muted),
                  ],
                ],
              ),
            ),
            const SizedBox(width: 8),
            const Icon(Icons.add_circle_outline_rounded,
                size: 18, color: AppColors.muted),
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
    OutlineInputBorder border(Color c) => OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: c),
        );
    return DropdownButtonFormField<String>(
      initialValue: value,
      isExpanded: true,
      dropdownColor: AppColors.surface,
      style: AppTextStyles.body,
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: AppColors.secondaryText),
        filled: true,
        fillColor: AppColors.surfaceAlt,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        enabledBorder: border(AppColors.border),
        focusedBorder: border(AppColors.cyan),
        disabledBorder: border(AppColors.border),
      ),
      items: items.entries
          .map((e) => DropdownMenuItem(
                value: e.key,
                child: Text(e.value, overflow: TextOverflow.ellipsis),
              ))
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

  Future<void> _download(BuildContext context) async {
    final messenger = ScaffoldMessenger.of(context);
    bool ok = false;
    try {
      ok = await launchUrl(Uri.parse(videoUrl), mode: LaunchMode.externalApplication);
    } catch (_) {
      ok = false;
    }
    if (!ok) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Não foi possível abrir o download.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = status;
    final isReady = s?.status == 'ready';
    final isFailed = s?.status == 'failed' || s?.status == 'cancelled';
    final progress = s?.progress ?? 0.0;
    final color = isReady
        ? AppColors.success
        : isFailed
            ? AppColors.danger
            : AppColors.cyan;

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
                color: color,
                size: 20,
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppColors.background,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(heading,
                    style: const TextStyle(
                        color: AppColors.secondaryText,
                        fontSize: 11,
                        fontWeight: FontWeight.w800)),
              ),
              const SizedBox(width: 8),
              Expanded(child: Text(label, style: AppTextStyles.cardTitle)),
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
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: DFPrimaryButton(
                label: 'Baixar vídeo',
                icon: Icons.download_rounded,
                onPressed: () => _download(context),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
