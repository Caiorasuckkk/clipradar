import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api_client.dart';
import '../models/review_clip.dart';
import '../models/review_summary.dart';
import '../widgets/clip_video_player.dart';
import '../widgets/rating_stars.dart';
import '../widgets/reason_chips.dart';
import '../widgets/status_buttons.dart';
import '../widgets/summary_card.dart';
import 'reviewed_clips_screen.dart';

enum ClipFilter { pending, reviewed, all }

class ReviewClipScreen extends StatefulWidget {
  const ReviewClipScreen({super.key});

  @override
  State<ReviewClipScreen> createState() => _ReviewClipScreenState();
}

class _ReviewClipScreenState extends State<ReviewClipScreen> {
  final ApiClient _api = ApiClient();
  final TextEditingController _notesController = TextEditingController();
  final Set<String> _skippedClipIds = {};

  ReviewClip? _clip;
  ReviewSummary? _summary;
  List<ReviewClip> _clips = [];
  ClipFilter _filter = ClipFilter.pending;
  bool _loading = true;
  bool _saving = false;
  String? _error;
  int? _rating;
  String? _status;
  String _reason = '';

  @override
  void initState() {
    super.initState();
    _loadInitial();
  }

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _loadInitial({ReviewClip? focusClip}) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final summary = await _api.fetchSummary();
      final clips = await _api.fetchClips();
      final next = focusClip ?? _chooseNextPending(clips);
      if (!mounted) return;
      setState(() {
        _summary = summary;
        _clips = clips;
        _clip = next;
        _loading = false;
      });
      _fillForm(next);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _loading = false;
      });
    }
  }

  ReviewClip? _chooseNextPending(List<ReviewClip> clips) {
    final pending = clips.where((clip) => !clip.alreadyReviewed).toList();
    if (pending.isEmpty) return null;
    for (final clip in pending) {
      if (!_skippedClipIds.contains(clip.clipId)) return clip;
    }
    _skippedClipIds.clear();
    return pending.first;
  }

  Future<void> _saveAndNext() async {
    final clip = _clip;
    if (clip == null || _saving) return;
    final wasUpdate = clip.alreadyReviewed;
    if (_rating == null || _status == null || _reason.trim().isEmpty) {
      _showSnack('Escolha uma nota, status e motivo antes de salvar.');
      return;
    }
    setState(() => _saving = true);
    try {
      await _api.saveReview(
        clipId: clip.clipId,
        status: _status!,
        rating: _rating!,
        reason: _reason.trim(),
        notes: _notesController.text.trim(),
      );
      _skippedClipIds.remove(clip.clipId);
      final summary = await _api.fetchSummary();
      final clips = await _api.fetchClips();
      final next = wasUpdate
          ? _findClip(clips, clip.clipId)
          : _chooseNextPending(clips);
      if (!mounted) return;
      setState(() {
        _summary = summary;
        _clips = clips;
        _clip = next;
        _saving = false;
        _error = null;
      });
      _fillForm(_clip);
      _showSnack(clip.alreadyReviewed ? 'Review atualizada.' : 'Review salva.');
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _saving = false;
      });
    }
  }

  Future<void> _skip() async {
    final clip = _clip;
    if (clip == null || _saving) return;
    _skippedClipIds.add(clip.clipId);
    final next = _chooseNextPending(_clips);
    setState(() => _clip = next);
    _fillForm(next);
  }

  void _fillForm(ReviewClip? clip) {
    final review = clip?.currentReview;
    _notesController.text = review?.notes ?? '';
    _rating = review?.rating;
    _reason = review?.reason ?? '';
    _status = review?.status.isNotEmpty == true ? review!.status : null;
  }

  void _selectClip(ReviewClip clip) {
    setState(() {
      _clip = clip;
      _filter = ClipFilter.pending;
    });
    _fillForm(clip);
  }

  ReviewClip? _findClip(List<ReviewClip> clips, String clipId) {
    for (final clip in clips) {
      if (clip.clipId == clipId) return clip;
    }
    return null;
  }

  Future<void> _openYoutube() async {
    final url = _clip?.youtubeUrl ?? '';
    if (url.isEmpty) {
      _showSnack('Este clipe nao tem youtube_url.');
      return;
    }
    final uri = Uri.parse(url);
    final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened) _showSnack('Nao foi possivel abrir o YouTube.');
  }

  void _showSnack(String message) {
    if (!mounted) return;
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
    return Scaffold(
      body: SafeArea(
        child: Container(
          color: const Color(0xFF08090E),
          child: Column(
            children: [
              _Header(
                summary: _summary,
                filter: _filter,
                onFilterChanged: (filter) => setState(() => _filter = filter),
                onRefresh: () => _loadInitial(focusClip: _clip),
              ),
              Expanded(child: _body()),
              if (_filter == ClipFilter.pending || _clip != null)
                _BottomActions(
                  isUpdate: _clip?.alreadyReviewed == true,
                  enabled: _clip != null && !_loading,
                  saving: _saving,
                  onSave: _saveAndNext,
                  onSkip: _filter == ClipFilter.pending ? _skip : null,
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _body() {
    if (_loading) {
      return const Center(
        child: CircularProgressIndicator(color: Color(0xFF00C8F0)),
      );
    }
    if (_error != null && _clips.isEmpty) {
      return _CenteredMessage(
        icon: Icons.wifi_off_rounded,
        title: 'Backend indisponivel',
        detail: _error!,
        onRetry: _loadInitial,
      );
    }
    if (_filter == ClipFilter.reviewed || _filter == ClipFilter.all) {
      final list = _filter == ClipFilter.reviewed
          ? _clips.where((clip) => clip.alreadyReviewed).toList()
          : _clips;
      return ReviewedClipsScreen(
        clips: list,
        emptyTitle: _filter == ClipFilter.reviewed
            ? 'Nenhum clipe revisado ainda.'
            : 'Nenhum clipe exportado encontrado.',
        onClipTap: _selectClip,
      );
    }
    final clip = _clip;
    if (clip == null) {
      return _CenteredMessage(
        icon: Icons.done_all_rounded,
        title: 'Sem clipes pendentes',
        detail: 'Todos os exports foram revisados. Use Revisados para editar.',
        onRetry: _loadInitial,
      );
    }
    final videoUrl = _api.exportUrl(clip.outputFilename);
    return RefreshIndicator(
      color: const Color(0xFF00C8F0),
      backgroundColor: const Color(0xFF0F1018),
      onRefresh: _loadInitial,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 18),
        children: [
          if (_error != null) _InlineError(message: _error!),
          _ProgressHint(
            summary: _summary,
            skippedCount: _skippedClipIds.length,
          ),
          const SizedBox(height: 12),
          ClipVideoPlayer(url: videoUrl),
          const SizedBox(height: 12),
          _ClipInfoCard(clip: clip, onOpenYoutube: _openYoutube),
          const SizedBox(height: 12),
          RatingStars(
            value: _rating ?? 0,
            onChanged: (value) => setState(() => _rating = value),
          ),
          const SizedBox(height: 12),
          StatusButtons(
            value: _status ?? '',
            onChanged: (value) => setState(() => _status = value),
          ),
          const SizedBox(height: 12),
          ReasonChips(
            selected: _reason,
            onChanged: (value) => setState(() => _reason = value),
          ),
          const SizedBox(height: 12),
          _NotesField(controller: _notesController),
        ],
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.summary,
    required this.filter,
    required this.onFilterChanged,
    required this.onRefresh,
  });

  final ReviewSummary? summary;
  final ClipFilter filter;
  final ValueChanged<ClipFilter> onFilterChanged;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1018).withValues(alpha: 0.98),
        border: Border(
          bottom: BorderSide(color: Colors.white.withValues(alpha: 0.06)),
        ),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: const Color(0xFF00C8F0).withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(
                  Icons.playlist_play_rounded,
                  color: Color(0xFF00C8F0),
                ),
              ),
              const SizedBox(width: 10),
              const Expanded(
                child: Text.rich(
                  TextSpan(
                    children: [
                      TextSpan(
                        text: 'DarkFlow',
                        style: TextStyle(color: Color(0xFF00C8F0)),
                      ),
                      TextSpan(
                        text: ' Review',
                        style: TextStyle(color: Color(0xFFE8EAF0)),
                      ),
                    ],
                  ),
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
                ),
              ),
              Text(
                '${summary?.pending ?? 0} pend.',
                style: const TextStyle(color: Color(0xFF6B7280), fontSize: 12),
              ),
            ],
          ),
          const SizedBox(height: 10),
          SummaryCard(summary: summary, onRefresh: onRefresh),
          const SizedBox(height: 10),
          SegmentedButton<ClipFilter>(
            segments: const [
              ButtonSegment(
                value: ClipFilter.pending,
                label: Text('Pendentes'),
                icon: Icon(Icons.queue_play_next_rounded),
              ),
              ButtonSegment(
                value: ClipFilter.reviewed,
                label: Text('Revisados'),
                icon: Icon(Icons.fact_check_rounded),
              ),
              ButtonSegment(
                value: ClipFilter.all,
                label: Text('Todos'),
                icon: Icon(Icons.video_library_rounded),
              ),
            ],
            selected: {filter},
            onSelectionChanged: (value) => onFilterChanged(value.first),
            style: SegmentedButton.styleFrom(
              selectedBackgroundColor: const Color(
                0xFF00C8F0,
              ).withValues(alpha: 0.16),
              selectedForegroundColor: const Color(0xFF00C8F0),
              foregroundColor: const Color(0xFF8C93A6),
              side: BorderSide(color: Colors.white.withValues(alpha: 0.08)),
            ),
          ),
        ],
      ),
    );
  }
}

class _ProgressHint extends StatelessWidget {
  const _ProgressHint({required this.summary, required this.skippedCount});

  final ReviewSummary? summary;
  final int skippedCount;

  @override
  Widget build(BuildContext context) {
    final reviewed = summary?.totalReviewed ?? 0;
    final total = summary?.totalExported ?? 0;
    final pending = summary?.pending ?? 0;
    return Row(
      children: [
        Text(
          'Clipe ${total == 0 ? 0 : reviewed + 1} de $total',
          style: const TextStyle(color: Color(0xFF6B7280), fontSize: 12),
        ),
        const SizedBox(width: 10),
        Text(
          'Pendentes: $pending',
          style: const TextStyle(color: Color(0xFF00C8F0), fontSize: 12),
        ),
        if (skippedCount > 0) ...[
          const SizedBox(width: 10),
          Text(
            'Pulados: $skippedCount',
            style: const TextStyle(color: Color(0xFFF59E0B), fontSize: 12),
          ),
        ],
      ],
    );
  }
}

class _ClipInfoCard extends StatelessWidget {
  const _ClipInfoCard({required this.clip, required this.onOpenYoutube});

  final ReviewClip clip;
  final VoidCallback onOpenYoutube;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1018),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withValues(alpha: 0.07)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'CLIPE ATUAL',
                  style: TextStyle(
                    color: Color(0xFF6B7280),
                    fontSize: 10,
                    letterSpacing: 0.9,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              TextButton.icon(
                onPressed: clip.youtubeUrl.isEmpty ? null : onOpenYoutube,
                icon: const Icon(Icons.open_in_new_rounded, size: 15),
                label: const Text('Abrir YouTube'),
              ),
            ],
          ),
          const SizedBox(height: 7),
          Text(
            clip.videoTitle,
            style: const TextStyle(
              color: Color(0xFFE8EAF0),
              fontSize: 17,
              height: 1.24,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 12),
          _InfoRow(
            icon: Icons.tag_rounded,
            label: 'clip_id',
            value: clip.clipId,
            accent: true,
          ),
          _InfoRow(
            icon: Icons.schedule_rounded,
            label: 'tempo',
            value: clip.timeRange,
          ),
          _InfoRow(
            icon: Icons.star_half_rounded,
            label: 'original',
            value: 'rating ${clip.reviewRating ?? '-'} / ${clip.reviewReason}',
          ),
          _InfoRow(
            icon: Icons.bolt_rounded,
            label: 'source',
            value:
                '${clip.sourceQualityTier ?? '-'} ${clip.sourceQualityScore ?? ''}'
                    .trim(),
          ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.icon,
    required this.label,
    required this.value,
    this.accent = false,
  });

  final IconData icon;
  final String label;
  final String value;
  final bool accent;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 9),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            icon,
            size: 16,
            color: accent ? const Color(0xFF00C8F0) : const Color(0xFF6B7280),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 72,
            child: Text(
              label.toUpperCase(),
              style: const TextStyle(
                color: Color(0xFF6B7280),
                fontSize: 10,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value.isEmpty ? '-' : value,
              style: TextStyle(
                color: accent
                    ? const Color(0xFF00C8F0)
                    : const Color(0xFFC0C4D6),
                fontSize: 13,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _NotesField extends StatelessWidget {
  const _NotesField({required this.controller});

  final TextEditingController controller;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      minLines: 3,
      maxLines: 5,
      style: const TextStyle(color: Color(0xFFE8EAF0)),
      decoration: InputDecoration(
        labelText: 'Notes opcionais',
        labelStyle: const TextStyle(color: Color(0xFF6B7280)),
        filled: true,
        fillColor: const Color(0xFF0F1018),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.07)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: Color(0xFF00C8F0)),
        ),
      ),
    );
  }
}

class _BottomActions extends StatelessWidget {
  const _BottomActions({
    required this.isUpdate,
    required this.enabled,
    required this.saving,
    required this.onSave,
    required this.onSkip,
  });

  final bool isUpdate;
  final bool enabled;
  final bool saving;
  final VoidCallback onSave;
  final VoidCallback? onSkip;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            const Color(0xFF08090E).withValues(alpha: 0),
            const Color(0xFF08090E),
          ],
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: double.infinity,
            height: 56,
            child: FilledButton.icon(
              onPressed: enabled && !saving ? onSave : null,
              style: FilledButton.styleFrom(
                backgroundColor: const Color(0xFF00C8F0),
                foregroundColor: const Color(0xFF08090E),
                disabledBackgroundColor: const Color(0xFF1A1C28),
                disabledForegroundColor: const Color(0xFF6B7280),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(18),
                ),
              ),
              icon: saving
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Icon(
                      isUpdate
                          ? Icons.save_as_rounded
                          : Icons.skip_next_rounded,
                    ),
              label: Text(
                saving
                    ? 'Salvando...'
                    : isUpdate
                    ? 'Atualizar review'
                    : 'Salvar e proximo',
              ),
            ),
          ),
          if (onSkip != null)
            TextButton(
              onPressed: enabled && !saving ? onSkip : null,
              child: const Text('Pular'),
            ),
        ],
      ),
    );
  }
}

class _CenteredMessage extends StatelessWidget {
  const _CenteredMessage({
    required this.icon,
    required this.title,
    required this.detail,
    required this.onRetry,
  });

  final IconData icon;
  final String title;
  final String detail;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: const Color(0xFF00C8F0), size: 48),
            const SizedBox(height: 14),
            Text(
              title,
              style: const TextStyle(
                color: Color(0xFFE8EAF0),
                fontSize: 18,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              detail,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Color(0xFF8C93A6)),
            ),
            const SizedBox(height: 18),
            OutlinedButton(onPressed: onRetry, child: const Text('Recarregar')),
          ],
        ),
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
        border: Border.all(
          color: const Color(0xFFEF4444).withValues(alpha: 0.28),
        ),
      ),
      child: Text(
        message,
        style: const TextStyle(color: Color(0xFFFCA5A5), fontSize: 12),
      ),
    );
  }
}
