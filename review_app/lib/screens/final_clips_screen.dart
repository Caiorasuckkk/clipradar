import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../models/final_clip.dart';
import '../models/final_summary.dart';
import '../widgets/clip_video_player.dart';
import '../widgets/rating_stars.dart';

enum FinalFilter { pending, reviewed, ready, all }

class FinalClipsScreen extends StatefulWidget {
  const FinalClipsScreen({super.key});

  @override
  State<FinalClipsScreen> createState() => _FinalClipsScreenState();
}

class _FinalClipsScreenState extends State<FinalClipsScreen> {
  final ApiClient _api = ApiClient();
  final TextEditingController _notesController = TextEditingController();

  FinalClip? _clip;
  FinalSummary? _summary;
  List<FinalClip> _clips = [];
  FinalFilter _filter = FinalFilter.pending;
  bool _loading = true;
  bool _saving = false;
  bool _showDetail = false;
  String? _error;
  int? _rating;
  String? _status;
  String _reason = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _load({FinalClip? focusClip}) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final summary = await _api.fetchFinalSummary();
      final clips = await _api.fetchFinalClips(status: _statusQuery(_filter));
      final next = focusClip ?? (clips.isEmpty ? null : clips.first);
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

  String _statusQuery(FinalFilter filter) {
    return switch (filter) {
      FinalFilter.pending => 'pending',
      FinalFilter.reviewed => 'reviewed',
      FinalFilter.ready => 'ready',
      FinalFilter.all => 'all',
    };
  }

  void _fillForm(FinalClip? clip) {
    final review = clip?.currentFinalReview;
    _notesController.text = review?.notes ?? '';
    _rating = review?.rating;
    _status = review?.status.isNotEmpty == true ? review!.status : null;
    _reason = review?.reason ?? '';
  }

  Future<void> _changeFilter(FinalFilter filter) async {
    setState(() {
      _filter = filter;
      _showDetail = false;
    });
    await _load();
  }

  Future<void> _saveAndNext() async {
    final clip = _clip;
    if (clip == null || _saving) return;
    if (_rating == null || _status == null || _reason.trim().isEmpty) {
      _showSnack('Escolha nota, status e motivo antes de salvar.');
      return;
    }
    setState(() => _saving = true);
    try {
      await _api.saveFinalReview(
        finalClipId: clip.finalClipId,
        status: _status!,
        rating: _rating!,
        reason: _reason.trim(),
        notes: _notesController.text.trim(),
      );
      final summary = await _api.fetchFinalSummary();
      final clips = await _api.fetchFinalClips(status: _statusQuery(_filter));
      if (!mounted) return;
      setState(() {
        _summary = summary;
        _clips = clips;
        _clip = clips.isEmpty ? null : clips.first;
        _showDetail = false;
        _saving = false;
        _error = null;
      });
      _fillForm(_clip);
      _showSnack('Review final salva.');
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _saving = false;
      });
    }
  }

  void _selectClip(FinalClip clip) {
    setState(() {
      _clip = clip;
      _showDetail = true;
    });
    _fillForm(clip);
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
              _FinalHeader(
                summary: _summary,
                filter: _filter,
                onFilterChanged: _changeFilter,
                onRefresh: () => _load(focusClip: _clip),
              ),
              Expanded(child: _body()),
              if (_clip != null &&
                  (_filter == FinalFilter.pending || _showDetail))
                _FinalBottomActions(saving: _saving, onSave: _saveAndNext),
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
        onRetry: _load,
      );
    }
    if (_filter != FinalFilter.pending && _clips.isNotEmpty && !_showDetail) {
      return _FinalClipList(clips: _clips, onClipTap: _selectClip);
    }
    final clip = _clip;
    if (clip == null) {
      return _CenteredMessage(
        icon: Icons.done_all_rounded,
        title: 'Sem finais pendentes',
        detail: 'Os clipes finais desta fila ja foram revisados.',
        onRetry: _load,
      );
    }
    return RefreshIndicator(
      color: const Color(0xFF00C8F0),
      backgroundColor: const Color(0xFF0F1018),
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 18),
        children: [
          if (_error != null) _InlineError(message: _error!),
          ClipVideoPlayer(
            url: _api.finalExportUrl(clip.finalFilename),
            aspectRatio: 9 / 16,
          ),
          const SizedBox(height: 12),
          _FinalInfoCard(clip: clip),
          const SizedBox(height: 12),
          RatingStars(
            value: _rating ?? 0,
            onChanged: (value) => setState(() => _rating = value),
          ),
          const SizedBox(height: 12),
          _FinalStatusButtons(
            value: _status ?? '',
            onChanged: (value) => setState(() => _status = value),
          ),
          const SizedBox(height: 12),
          _FinalReasonChips(
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

class _FinalHeader extends StatelessWidget {
  const _FinalHeader({
    required this.summary,
    required this.filter,
    required this.onFilterChanged,
    required this.onRefresh,
  });

  final FinalSummary? summary;
  final FinalFilter filter;
  final ValueChanged<FinalFilter> onFilterChanged;
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
              const Icon(Icons.rocket_launch_rounded, color: Color(0xFF00C8F0)),
              const SizedBox(width: 10),
              const Expanded(
                child: Text(
                  'Final Clips',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
                ),
              ),
              IconButton(
                onPressed: onRefresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          const SizedBox(height: 8),
          _FinalSummaryCard(summary: summary),
          const SizedBox(height: 10),
          SegmentedButton<FinalFilter>(
            segments: const [
              ButtonSegment(value: FinalFilter.pending, label: Text('Pend.')),
              ButtonSegment(value: FinalFilter.reviewed, label: Text('Rev.')),
              ButtonSegment(value: FinalFilter.ready, label: Text('Prontos')),
              ButtonSegment(value: FinalFilter.all, label: Text('Todos')),
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

class _FinalSummaryCard extends StatelessWidget {
  const _FinalSummaryCard({required this.summary});

  final FinalSummary? summary;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF08090E),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withValues(alpha: 0.07)),
      ),
      child: Wrap(
        spacing: 14,
        runSpacing: 7,
        children: [
          _Metric('Total', '${summary?.totalFinal ?? 0}', Colors.white70),
          _Metric('Pend.', '${summary?.pending ?? 0}', const Color(0xFF00C8F0)),
          _Metric(
            'Ready',
            '${summary?.readyToPost ?? 0}',
            const Color(0xFF10B981),
          ),
          _Metric(
            'Edit',
            '${summary?.needsEdit ?? 0}',
            const Color(0xFFF59E0B),
          ),
          _Metric('No', '${summary?.doNotPost ?? 0}', const Color(0xFFEF4444)),
          _Metric(
            'Avg',
            summary?.averageRating?.toStringAsFixed(1) ?? '-',
            Colors.white70,
          ),
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric(this.label, this.value, this.color);

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          value,
          style: TextStyle(
            color: color,
            fontWeight: FontWeight.w800,
            fontSize: 16,
          ),
        ),
        Text(
          label,
          style: const TextStyle(color: Color(0xFF6B7280), fontSize: 10),
        ),
      ],
    );
  }
}

class _FinalClipList extends StatelessWidget {
  const _FinalClipList({required this.clips, required this.onClipTap});

  final List<FinalClip> clips;
  final ValueChanged<FinalClip> onClipTap;

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.all(14),
      itemCount: clips.length,
      separatorBuilder: (_, _) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final clip = clips[index];
        return ListTile(
          onTap: () => onClipTap(clip),
          tileColor: const Color(0xFF0F1018),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          leading: const Icon(
            Icons.movie_filter_rounded,
            color: Color(0xFF00C8F0),
          ),
          title: Text(
            clip.videoTitle.isEmpty ? clip.finalFilename : clip.videoTitle,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          subtitle: Text(
            '${clip.postStatus} · rating ${clip.rating ?? '-'} · ${clip.reason}',
          ),
        );
      },
    );
  }
}

class _FinalInfoCard extends StatelessWidget {
  const _FinalInfoCard({required this.clip});

  final FinalClip clip;

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
          const Text(
            'FINAL CLIP',
            style: TextStyle(
              color: Color(0xFF6B7280),
              fontSize: 10,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.8,
            ),
          ),
          const SizedBox(height: 7),
          Text(
            clip.videoTitle.isEmpty ? clip.finalFilename : clip.videoTitle,
            style: const TextStyle(
              color: Color(0xFFE8EAF0),
              fontSize: 17,
              height: 1.24,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 12),
          _InfoRow(label: 'final_id', value: clip.finalClipId),
          _InfoRow(label: 'tempo', value: clip.timeRange),
          _InfoRow(
            label: 'origem',
            value: 'rating ${clip.rating ?? '-'} / ${clip.reason}',
          ),
          _InfoRow(label: 'post', value: clip.postStatus),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
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
              style: const TextStyle(color: Color(0xFFC0C4D6), fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
}

class _FinalStatusButtons extends StatelessWidget {
  const _FinalStatusButtons({required this.value, required this.onChanged});

  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    const options = [
      (
        'ready_to_post',
        'Pronto',
        Icons.check_circle_rounded,
        Color(0xFF10B981),
      ),
      ('needs_edit', 'Editar', Icons.tune_rounded, Color(0xFFF59E0B)),
      ('do_not_post', 'Nao postar', Icons.block_rounded, Color(0xFFEF4444)),
    ];
    return Row(
      children: options.map((option) {
        final active = value == option.$1;
        return Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: InkWell(
              borderRadius: BorderRadius.circular(16),
              onTap: () => onChanged(option.$1),
              child: Container(
                height: 64,
                decoration: BoxDecoration(
                  color: active
                      ? option.$4.withValues(alpha: 0.16)
                      : const Color(0xFF0F1018),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: active
                        ? option.$4.withValues(alpha: 0.55)
                        : Colors.white.withValues(alpha: 0.07),
                  ),
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      option.$3,
                      color: active ? option.$4 : const Color(0xFF6B7280),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      option.$2,
                      style: TextStyle(
                        color: active ? option.$4 : const Color(0xFF6B7280),
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      }).toList(),
    );
  }
}

class _FinalReasonChips extends StatelessWidget {
  const _FinalReasonChips({required this.selected, required this.onChanged});

  final String selected;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    const reasons = [
      'pronto',
      'bom_final',
      'excelente_final',
      'sem_contexto',
      'corte_ruim',
      'qualidade_ruim',
      'precisa_legenda',
      'precisa_template',
      'nao_postar',
    ];
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1018),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withValues(alpha: 0.07)),
      ),
      child: Wrap(
        spacing: 7,
        runSpacing: 7,
        children: reasons.map((reason) {
          final active = selected == reason;
          return ChoiceChip(
            selected: active,
            label: Text(reason),
            onSelected: (_) => onChanged(reason),
            labelStyle: TextStyle(
              color: active ? const Color(0xFF00C8F0) : const Color(0xFF9CA3AF),
              fontSize: 12,
              fontWeight: active ? FontWeight.w800 : FontWeight.w500,
            ),
            selectedColor: const Color(0xFF00C8F0).withValues(alpha: 0.16),
            backgroundColor: const Color(0xFF1A1C28),
            side: BorderSide(color: Colors.white.withValues(alpha: 0.07)),
            showCheckmark: false,
          );
        }).toList(),
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
      ),
    );
  }
}

class _FinalBottomActions extends StatelessWidget {
  const _FinalBottomActions({required this.saving, required this.onSave});

  final bool saving;
  final VoidCallback onSave;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 16),
      child: SizedBox(
        width: double.infinity,
        height: 56,
        child: FilledButton.icon(
          onPressed: saving ? null : onSave,
          icon: saving
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.skip_next_rounded),
          label: Text(saving ? 'Salvando...' : 'Salvar e proximo'),
        ),
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
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
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
      ),
      child: Text(
        message,
        style: const TextStyle(color: Color(0xFFFCA5A5), fontSize: 12),
      ),
    );
  }
}
