import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/api_client.dart';
import '../models/post_item.dart';
import '../models/posts_summary.dart';
import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import '../widgets/clip_video_player.dart';
import '../widgets/df_card.dart';
import '../widgets/df_empty_state.dart';
import '../widgets/df_loading_state.dart';
import '../widgets/df_status_chip.dart';

enum PostFilter { notPosted, posted, scheduled, doNotPost, all }

class PostsScreen extends StatefulWidget {
  const PostsScreen({super.key});

  @override
  State<PostsScreen> createState() => _PostsScreenState();
}

class _PostsScreenState extends State<PostsScreen> {
  final ApiClient _api = ApiClient();
  final TextEditingController _notesController = TextEditingController();
  final TextEditingController _urlController = TextEditingController();

  PostsSummary? _summary;
  ApprovedGenerationStatus? _generationStatus;
  List<PostItem> _posts = [];
  PostItem? _selected;
  PostFilter _filter = PostFilter.notPosted;
  bool _loading = true;
  bool _saving = false;
  final Set<String> _platforms = {};
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _notesController.dispose();
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _load({PostItem? focus}) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final summary = await _api.fetchPostsSummary();
      final generationStatus = await _api.fetchApprovedGenerationStatus();
      final posts = await _api.fetchPosts(status: _statusQuery(_filter));
      final selected = focus ?? (posts.isEmpty ? null : posts.first);
      if (!mounted) return;
      setState(() {
        _summary = summary;
        _generationStatus = generationStatus;
        _posts = posts;
        _selected = selected;
        _loading = false;
      });
      _fill(selected);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _loading = false;
      });
    }
  }

  void _fill(PostItem? post) {
    _notesController.text = post?.notes ?? '';
    _urlController.text = post?.postUrl ?? '';
    _platforms
      ..clear()
      ..addAll(post?.postedPlatforms ?? const []);
  }

  Future<void> _changeFilter(PostFilter filter) async {
    setState(() => _filter = filter);
    await _load();
  }

  Future<void> _save(String status) async {
    final post = _selected;
    if (post == null || _saving) return;
    setState(() => _saving = true);
    try {
      await _api.updatePostStatus(
        postId: post.postId,
        status: status,
        platforms: _platforms.toList(),
        postedAt: status == 'posted' ? DateTime.now().toIso8601String() : '',
        postUrl: _urlController.text.trim(),
        notes: _notesController.text.trim(),
      );
      if (!mounted) return;
      setState(() => _saving = false);
      _showSnack('Status atualizado.');
      await _load();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _saving = false;
      });
    }
  }

  Future<void> _copy(String label, String text) async {
    await Clipboard.setData(ClipboardData(text: text));
    _showSnack('$label copiado.');
  }

  void _select(PostItem post) {
    setState(() => _selected = post);
    _fill(post);
  }

  void _nextNotPosted() {
    final candidates = _posts
        .where((post) => post.postedStatus == 'not_posted')
        .toList();
    if (candidates.isEmpty) return;
    final current = _selected;
    final index = current == null ? -1 : candidates.indexOf(current);
    final next = candidates[(index + 1) % candidates.length];
    _select(next);
  }

  String _statusQuery(PostFilter filter) {
    return switch (filter) {
      PostFilter.notPosted => 'not_posted',
      PostFilter.posted => 'posted',
      PostFilter.scheduled => 'scheduled',
      PostFilter.doNotPost => 'do_not_post',
      PostFilter.all => 'all',
    };
  }

  void _showSnack(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: const Color(0xFF1A1C28),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final post = _selected;
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            _PostsHeader(
              summary: _summary,
              generationStatus: _generationStatus,
              filter: _filter,
              onFilterChanged: _changeFilter,
              onRefresh: () => _load(focus: _selected),
            ),
            Expanded(
              child: _loading
                  ? const DfLoadingState(message: 'Carregando posts...')
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: ListView(
                        padding: const EdgeInsets.all(14),
                        children: [
                          if (_error != null) _InlineError(message: _error!),
                          if (_generationStatus?.running == true ||
                              (_generationStatus?.pendingCount ?? 0) > 0)
                            const _GenerationBanner(),
                          if (_generationStatus?.running == true ||
                              (_generationStatus?.pendingCount ?? 0) > 0)
                            const SizedBox(height: 12),
                          if (_posts.isNotEmpty)
                            _PostPicker(
                              posts: _posts,
                              selected: post,
                              onSelect: _select,
                            ),
                          const SizedBox(height: 12),
                          if (post == null)
                            const DfEmptyState(
                              icon: Icons.publish_rounded,
                              title: 'Nenhum post',
                              message:
                                  'Gere metadados em Operações ou troque o filtro.',
                            )
                          else ...[
                            ClipVideoPlayer(
                              url: _api.postingPackageVideoUrl(
                                post.packageVideoFilename,
                              ),
                              aspectRatio: 9 / 16,
                            ),
                            const SizedBox(height: 12),
                            _PostInfoCard(post: post),
                            const SizedBox(height: 12),
                            _CopyCard(post: post, onCopy: _copy),
                            const SizedBox(height: 12),
                            _PlatformSelector(
                              selected: _platforms,
                              onChanged: () => setState(() {}),
                            ),
                            const SizedBox(height: 12),
                            _PostFields(
                              notesController: _notesController,
                              urlController: _urlController,
                            ),
                            const SizedBox(height: 12),
                            _PostActions(
                              saving: _saving,
                              onPosted: () => _save('posted'),
                              onScheduled: () => _save('scheduled'),
                              onNotPosted: () => _save('not_posted'),
                              onDoNotPost: () => _save('do_not_post'),
                              onNext: _nextNotPosted,
                            ),
                          ],
                        ],
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PostsHeader extends StatelessWidget {
  const _PostsHeader({
    required this.summary,
    required this.generationStatus,
    required this.filter,
    required this.onFilterChanged,
    required this.onRefresh,
  });

  final PostsSummary? summary;
  final ApprovedGenerationStatus? generationStatus;
  final PostFilter filter;
  final ValueChanged<PostFilter> onFilterChanged;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1018),
        border: Border(
          bottom: BorderSide(color: Colors.white.withValues(alpha: 0.06)),
        ),
      ),
      child: Column(
        children: [
          Row(
            children: [
              const Icon(Icons.publish_rounded, color: AppColors.cyan),
              const SizedBox(width: 10),
              const Expanded(
                child: Text('Posts', style: AppTextStyles.section),
              ),
              IconButton(
                onPressed: onRefresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          const SizedBox(height: 8),
          _SummaryStrip(summary: summary),
          if (generationStatus?.running == true ||
              (generationStatus?.pendingCount ?? 0) > 0) ...[
            const SizedBox(height: 8),
            const DfStatusChip(
              label: 'Gerando novos cortes aprovados...',
              status: 'scheduled',
            ),
          ],
          const SizedBox(height: 10),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: SegmentedButton<PostFilter>(
              segments: const [
                ButtonSegment(
                  value: PostFilter.notPosted,
                  label: Text('Novos'),
                ),
                ButtonSegment(
                  value: PostFilter.posted,
                  label: Text('Postados'),
                ),
                ButtonSegment(
                  value: PostFilter.scheduled,
                  label: Text('Agenda'),
                ),
                ButtonSegment(value: PostFilter.doNotPost, label: Text('Não')),
                ButtonSegment(value: PostFilter.all, label: Text('Todos')),
              ],
              selected: {filter},
              onSelectionChanged: (value) => onFilterChanged(value.first),
            ),
          ),
        ],
      ),
    );
  }
}

class _SummaryStrip extends StatelessWidget {
  const _SummaryStrip({required this.summary});

  final PostsSummary? summary;

  @override
  Widget build(BuildContext context) {
    final items = [
      ('Total', summary?.total ?? 0),
      ('Novos', summary?.notPosted ?? 0),
      ('Postados', summary?.posted ?? 0),
      ('Agenda', summary?.scheduled ?? 0),
      ('Não', summary?.doNotPost ?? 0),
    ];
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF08090E),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withValues(alpha: 0.07)),
      ),
      child: Wrap(
        spacing: 16,
        runSpacing: 8,
        children: items
            .map(
              (item) => Text(
                '${item.$1}: ${item.$2}',
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
            )
            .toList(),
      ),
    );
  }
}

class _GenerationBanner extends StatelessWidget {
  const _GenerationBanner();

  @override
  Widget build(BuildContext context) {
    return DfCard(
      child: Row(
        children: const [
          SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              'Gerando novos cortes aprovados. Toque em atualizar daqui a pouco.',
            ),
          ),
        ],
      ),
    );
  }
}

class _PostPicker extends StatelessWidget {
  const _PostPicker({
    required this.posts,
    required this.selected,
    required this.onSelect,
  });

  final List<PostItem> posts;
  final PostItem? selected;
  final ValueChanged<PostItem> onSelect;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 138,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: posts.length,
        separatorBuilder: (_, _) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final post = posts[index];
          final active = post.postId == selected?.postId;
          return SizedBox(
            width: 276,
            child: InkWell(
              onTap: () => onSelect(post),
              borderRadius: BorderRadius.circular(16),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: active ? AppColors.surfaceAlt : AppColors.surface,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: active ? AppColors.cyan : AppColors.border,
                  ),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 58,
                      height: 96,
                      decoration: BoxDecoration(
                        color: Colors.black,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppColors.border),
                      ),
                      child: const Icon(
                        Icons.play_arrow_rounded,
                        color: AppColors.cyan,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            post.suggestedTitle,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontWeight: FontWeight.w900),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            post.videoId,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppTextStyles.muted,
                          ),
                          const SizedBox(height: 8),
                          Align(
                            alignment: Alignment.centerLeft,
                            child: DfStatusChip(
                              label: post.postedStatus,
                              status: post.postedStatus,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _PostInfoCard extends StatelessWidget {
  const _PostInfoCard({required this.post});

  final PostItem post;

  @override
  Widget build(BuildContext context) {
    return DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            post.suggestedTitle,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 10),
          DfStatusChip(label: post.postedStatus, status: post.postedStatus),
          const SizedBox(height: 10),
          _Info('post_id', post.postId),
          _Info('arquivo', post.packageVideoFilename),
          _Info('status', post.postedStatus),
          _Info(
            'review',
            '${post.finalReviewRating ?? '-'} / ${post.finalReviewReason}',
          ),
        ],
      ),
    );
  }
}

class _CopyCard extends StatelessWidget {
  const _CopyCard({required this.post, required this.onCopy});

  final PostItem post;
  final Future<void> Function(String label, String text) onCopy;

  @override
  Widget build(BuildContext context) {
    return DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _CopyRow(label: 'Título', text: post.suggestedTitle, onCopy: onCopy),
          const SizedBox(height: 10),
          _CopyRow(
            label: 'Descrição',
            text: post.suggestedDescription,
            onCopy: onCopy,
          ),
          const SizedBox(height: 10),
          _CopyRow(label: 'Hashtags', text: post.hashtagsText, onCopy: onCopy),
        ],
      ),
    );
  }
}

class _CopyRow extends StatelessWidget {
  const _CopyRow({
    required this.label,
    required this.text,
    required this.onCopy,
  });

  final String label;
  final String text;
  final Future<void> Function(String label, String text) onCopy;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: const TextStyle(color: Color(0xFF8C93A6), fontSize: 12),
              ),
              const SizedBox(height: 3),
              Text(text.isEmpty ? '-' : text),
            ],
          ),
        ),
        IconButton(
          onPressed: text.isEmpty ? null : () => onCopy(label, text),
          icon: const Icon(Icons.copy_rounded),
        ),
      ],
    );
  }
}

class _PlatformSelector extends StatelessWidget {
  const _PlatformSelector({required this.selected, required this.onChanged});

  final Set<String> selected;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    const platforms = ['tiktok', 'instagram', 'youtube_shorts'];
    return DfCard(
      child: Wrap(
        spacing: 8,
        children: platforms.map((platform) {
          return FilterChip(
            selected: selected.contains(platform),
            label: Text(platform),
            onSelected: (active) {
              active ? selected.add(platform) : selected.remove(platform);
              onChanged();
            },
          );
        }).toList(),
      ),
    );
  }
}

class _PostFields extends StatelessWidget {
  const _PostFields({
    required this.notesController,
    required this.urlController,
  });

  final TextEditingController notesController;
  final TextEditingController urlController;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        TextField(
          controller: urlController,
          decoration: InputDecoration(
            labelText: 'URL do post',
            filled: true,
            fillColor: const Color(0xFF0F1018),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: BorderSide.none,
            ),
          ),
        ),
        const SizedBox(height: 10),
        TextField(
          controller: notesController,
          minLines: 2,
          maxLines: 4,
          decoration: InputDecoration(
            labelText: 'Notes',
            filled: true,
            fillColor: const Color(0xFF0F1018),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: BorderSide.none,
            ),
          ),
        ),
      ],
    );
  }
}

class _PostActions extends StatelessWidget {
  const _PostActions({
    required this.saving,
    required this.onPosted,
    required this.onScheduled,
    required this.onNotPosted,
    required this.onDoNotPost,
    required this.onNext,
  });

  final bool saving;
  final VoidCallback onPosted;
  final VoidCallback onScheduled;
  final VoidCallback onNotPosted;
  final VoidCallback onDoNotPost;
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        FilledButton.icon(
          onPressed: saving ? null : onPosted,
          icon: const Icon(Icons.check_rounded),
          label: const Text('Marcar postado'),
        ),
        OutlinedButton.icon(
          onPressed: saving ? null : onScheduled,
          icon: const Icon(Icons.schedule_rounded),
          label: const Text('Agendado'),
        ),
        OutlinedButton.icon(
          onPressed: saving ? null : onNotPosted,
          icon: const Icon(Icons.undo_rounded),
          label: const Text('Não postado'),
        ),
        OutlinedButton.icon(
          onPressed: saving ? null : onDoNotPost,
          icon: const Icon(Icons.block_rounded),
          label: const Text('Não postar'),
        ),
        OutlinedButton.icon(
          onPressed: saving ? null : onNext,
          icon: const Icon(Icons.skip_next_rounded),
          label: const Text('Próximo não postado'),
        ),
      ],
    );
  }
}

class _Info extends StatelessWidget {
  const _Info(this.label, this.value);

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Text(
        '$label: ${value.isEmpty ? '-' : value}',
        style: const TextStyle(color: Color(0xFFC0C4D6), fontSize: 13),
      ),
    );
  }
}

class _InlineError extends StatelessWidget {
  const _InlineError({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFEF4444).withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Text(message, style: const TextStyle(color: Color(0xFFFCA5A5))),
    );
  }
}
