import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/video_download.dart';
import '../models/generation_project.dart';
import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import '../widgets/clip_video_player.dart';
import '../widgets/df_button.dart';
import '../widgets/df_card.dart';
import '../widgets/df_error_state.dart';
import '../widgets/df_loading_state.dart';
import '../widgets/df_status_chip.dart';

/// Histórico de projetos gerados. Agrupa as versões por idioma (vídeos
/// bilíngues ficam sob o mesmo tema) e, ao expandir, mostra por idioma o
/// vídeo (assistir + baixar), os títulos, as legendas/roteiro e as hashtags.
class GenerationProjectsScreen extends StatefulWidget {
  const GenerationProjectsScreen({super.key});

  @override
  State<GenerationProjectsScreen> createState() =>
      _GenerationProjectsScreenState();
}

class _GenerationProjectsScreenState extends State<GenerationProjectsScreen> {
  final ApiClient _api = ApiClient();
  List<_ProjectGroup>? _groups;
  String? _error;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final projects = await _api.getGenerationProjects();
      if (!mounted) return;
      setState(() {
        _groups = _groupByTheme(projects);
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _loading = false;
      });
    }
  }

  /// Liga as versões de idioma de um mesmo tema: um filho aponta para o pai via
  /// [GenerationProject.bilingualParent]; o pai (e projetos de idioma único)
  /// usa o próprio id como raiz. A ordem dos projetos (mais recentes primeiro,
  /// vinda da API) é preservada na ordem dos grupos.
  List<_ProjectGroup> _groupByTheme(List<GenerationProject> projects) {
    final byRoot = <String, _ProjectGroup>{};
    final order = <String>[];
    for (final p in projects) {
      final root = p.bilingualParent.isNotEmpty ? p.bilingualParent : p.projectId;
      final group = byRoot.putIfAbsent(root, () {
        order.add(root);
        return _ProjectGroup(root);
      });
      group.langs.add(p);
    }
    for (final root in order) {
      byRoot[root]!.langs.sort(
        (a, b) => _langRank(a.language).compareTo(_langRank(b.language)),
      );
    }
    return [for (final root in order) byRoot[root]!];
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        scrolledUnderElevation: 0,
        title: const Text('Projetos'),
        actions: [
          IconButton(
            tooltip: 'Atualizar',
            onPressed: _loading ? null : _load,
            icon: _loading
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: SafeArea(child: _body()),
    );
  }

  Widget _body() {
    if (_loading && _groups == null) {
      return const DfLoadingState(message: 'Carregando projetos...');
    }
    if (_error != null && _groups == null) {
      return DfErrorState(message: _error!, onRetry: _load);
    }
    final groups = _groups ?? const [];
    if (groups.isEmpty) {
      return RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          children: const [
            SizedBox(height: 120),
            Center(
              child: Text(
                'Nenhum projeto gerado ainda.',
                style: TextStyle(color: AppColors.muted),
              ),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
        itemCount: groups.length,
        separatorBuilder: (_, _) => const SizedBox(height: 12),
        itemBuilder: (_, i) => _ProjectGroupCard(group: groups[i], api: _api),
      ),
    );
  }
}

class _ProjectGroup {
  _ProjectGroup(this.rootId);

  final String rootId;
  final List<GenerationProject> langs = [];

  /// Projeto exibido no cabeçalho (primeiro idioma após ordenação: pt-BR).
  GenerationProject get primary => langs.first;
}

class _ProjectGroupCard extends StatefulWidget {
  const _ProjectGroupCard({required this.group, required this.api});

  final _ProjectGroup group;
  final ApiClient api;

  @override
  State<_ProjectGroupCard> createState() => _ProjectGroupCardState();
}

class _ProjectGroupCardState extends State<_ProjectGroupCard> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final p = widget.group.primary;
    final langs = widget.group.langs;
    return DfCard(
      padding: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            borderRadius: BorderRadius.circular(18),
            onTap: () => setState(() => _expanded = !_expanded),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _Thumb(api: widget.api, project: p),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          p.title.isEmpty ? '(sem título)' : p.title,
                          style: AppTextStyles.cardTitle,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 6),
                        Text(
                          [
                            if (p.niche.isNotEmpty) p.niche,
                            if (p.createdAt.isNotEmpty) _shortDate(p.createdAt),
                          ].join('  ·  '),
                          style: AppTextStyles.muted,
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 6,
                          runSpacing: 6,
                          children: [
                            for (final l in langs)
                              DfStatusChip(label: _langShort(l.language)),
                            DfStatusChip(
                              label: _statusLabel(p.renderStatus),
                              status: p.renderStatus == 'ready'
                                  ? 'success'
                                  : p.renderStatus,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  Icon(
                    _expanded
                        ? Icons.keyboard_arrow_up_rounded
                        : Icons.keyboard_arrow_down_rounded,
                    color: AppColors.secondaryText,
                  ),
                ],
              ),
            ),
          ),
          if (_expanded) ...[
            const Divider(height: 1, color: AppColors.border),
            for (final l in langs)
              _LangSection(api: widget.api, project: l, multiLang: langs.length > 1),
          ],
        ],
      ),
    );
  }
}

class _Thumb extends StatelessWidget {
  const _Thumb({required this.api, required this.project});

  final ApiClient api;
  final GenerationProject project;

  @override
  Widget build(BuildContext context) {
    const w = 54.0;
    const h = 72.0;
    Widget placeholder() => Container(
          width: w,
          height: h,
          decoration: BoxDecoration(
            color: AppColors.surfaceAlt,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AppColors.border),
          ),
          child: const Icon(Icons.movie_creation_outlined,
              color: AppColors.muted, size: 22),
        );
    if (project.renderStatus != 'ready') return placeholder();
    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: Image.network(
        api.generationRenderThumbnailUrl(project.projectId),
        width: w,
        height: h,
        fit: BoxFit.cover,
        errorBuilder: (_, _, _) => placeholder(),
      ),
    );
  }
}

class _LangSection extends StatelessWidget {
  const _LangSection({
    required this.api,
    required this.project,
    required this.multiLang,
  });

  final ApiClient api;
  final GenerationProject project;
  final bool multiLang;

  @override
  Widget build(BuildContext context) {
    final p = project;
    final titles = p.publishTitles.isNotEmpty
        ? p.publishTitles
        : (p.title.isNotEmpty ? [p.title] : const <String>[]);
    final hashtags = p.publishHashtags.isNotEmpty ? p.publishHashtags : p.hashtags;
    final ready = p.renderStatus == 'ready';
    final videoUrl = api.generationRenderVideoUrl(p.projectId);

    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (multiLang)
            Row(
              children: [
                const Icon(Icons.translate_rounded,
                    size: 16, color: AppColors.cyan),
                const SizedBox(width: 6),
                Text(_langLong(p.language),
                    style: AppTextStyles.body.copyWith(
                        fontWeight: FontWeight.w700, color: AppColors.text)),
              ],
            ),
          if (multiLang) const SizedBox(height: 10),
          if (ready) ...[
            ClipVideoPlayer(url: videoUrl, aspectRatio: 9 / 16),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: DFSecondaryButton(
                label: 'Baixar vídeo',
                icon: Icons.download_rounded,
                onPressed: () => saveVideoToGallery(context, videoUrl),
              ),
            ),
          ] else
            _note('Sem vídeo renderizado para este idioma '
                '(status: ${_statusLabel(p.renderStatus)}).'),
          const SizedBox(height: 14),
          _block('Títulos', _bullets(titles)),
          _block(
            'Legendas / roteiro',
            p.scriptLines.isEmpty
                ? _note('Sem roteiro salvo.')
                : _bullets(p.scriptLines),
          ),
          if (hashtags.isNotEmpty) _block('Hashtags', _bullets(hashtags)),
          if (p.publishDescription.isNotEmpty)
            _block('Descrição', _note(p.publishDescription)),
        ],
      ),
    );
  }

  Widget _block(String label, Widget child) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label.toUpperCase(),
              style: AppTextStyles.muted.copyWith(
                  fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 0.5)),
          const SizedBox(height: 6),
          child,
        ],
      ),
    );
  }

  Widget _bullets(List<String> items) {
    if (items.isEmpty) return _note('—');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final item in items)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Padding(
                  padding: EdgeInsets.only(top: 7, right: 8),
                  child: CircleAvatar(radius: 2, backgroundColor: AppColors.cyan),
                ),
                Expanded(
                  child: Text(item,
                      style: AppTextStyles.body
                          .copyWith(color: AppColors.secondaryText)),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _note(String text) => Text(
        text,
        style: AppTextStyles.body.copyWith(color: AppColors.muted),
      );
}

// ---- helpers ----

int _langRank(String code) => code == 'pt-BR' ? 0 : (code == 'en-US' ? 1 : 2);

String _langShort(String code) {
  switch (code) {
    case 'pt-BR':
      return 'PT-BR';
    case 'en-US':
      return 'EN-US';
    default:
      return code.isEmpty ? '—' : code.toUpperCase();
  }
}

String _langLong(String code) {
  switch (code) {
    case 'pt-BR':
      return 'Português (pt-BR)';
    case 'en-US':
      return 'English (en-US)';
    default:
      return code.isEmpty ? 'Idioma' : code;
  }
}

String _statusLabel(String status) {
  switch (status) {
    case 'ready':
      return 'Pronto';
    case 'rendering':
    case 'running':
      return 'Renderizando';
    case 'failed':
      return 'Falhou';
    case 'none':
    case '':
      return 'Sem render';
    default:
      return status;
  }
}

String _shortDate(String iso) =>
    iso.length >= 10 ? iso.substring(0, 10) : iso;
