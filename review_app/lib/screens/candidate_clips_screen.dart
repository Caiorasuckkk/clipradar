import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../models/candidate_clip.dart';
import '../models/candidate_summary.dart';
import '../theme/app_colors.dart';
import '../widgets/clip_video_player.dart';
import '../widgets/df_button.dart';
import '../widgets/df_card.dart';
import '../widgets/df_error_state.dart';
import '../widgets/df_loading_state.dart';
import '../widgets/df_status_chip.dart';
import '../widgets/rating_stars.dart';
import 'processing_screen.dart';

enum CandidateFilter { pending, reviewed, all }

class CandidateClipsScreen extends StatefulWidget {
  const CandidateClipsScreen({super.key, this.onOpenHome, this.onOpenPosts});

  final VoidCallback? onOpenHome;
  final VoidCallback? onOpenPosts;

  @override
  State<CandidateClipsScreen> createState() => _CandidateClipsScreenState();
}

class _CandidateClipsScreenState extends State<CandidateClipsScreen> {
  final ApiClient _api = ApiClient();
  final TextEditingController _notesController = TextEditingController();

  CandidateSummary? _summary;
  ApprovedGenerationStatus? _generationStatus;
  List<CandidateClip> _clips = [];
  CandidateClip? _clip;
  final CandidateFilter _filter = CandidateFilter.pending;
  bool _loading = true;
  bool _saving = false;
  bool _startingFinals = false;
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

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final summary = await _api.fetchCandidateSummary();
      final generationStatus = await _api.fetchApprovedGenerationStatus();
      final loadedClips = await _api.fetchCandidateClips(
        status: _statusQuery(_filter),
      );
      final clips = _filterEvaluableClips(loadedClips);
      if (!mounted) return;
      setState(() {
        _summary = summary;
        _generationStatus = generationStatus;
        _clips = clips;
        _clip = clips.isEmpty ? null : clips.first;
        _loading = false;
      });
      _fillForm(_clip);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _loading = false;
      });
    }
  }

  List<CandidateClip> _filterEvaluableClips(List<CandidateClip> clips) {
    if (_filter != CandidateFilter.pending) {
      return clips;
    }
    return clips.where((clip) {
      final reviewed =
          clip.alreadyReviewed ||
          {
            'approved',
            'rejected',
            'needs_adjustment',
          }.contains(clip.currentReview?.status);
      final invalidPreview =
          clip.previewMissing || clip.previewInvalid || !clip.previewExists;
      if (reviewed) {
        debugPrint(
          '[CandidateClips] filtered reviewed candidate returned by pending: ${clip.candidateId}',
        );
      }
      return !reviewed && !invalidPreview;
    }).toList();
  }

  String _statusQuery(CandidateFilter filter) {
    return switch (filter) {
      CandidateFilter.pending => 'pending',
      CandidateFilter.reviewed => 'reviewed',
      CandidateFilter.all => 'all',
    };
  }

  void _fillForm(CandidateClip? clip) {
    final review = clip?.currentReview;
    _notesController.text = review?.notes ?? '';
    _rating = review?.rating;
    _status = review?.status.isNotEmpty == true ? review!.status : null;
    _reason = review?.reason ?? '';
  }

  Future<void> _saveAndNext() async {
    final clip = _clip;
    if (clip == null || _saving) return;
    final rating = _rating;
    final status = _status;
    final reason = _reason.trim();
    final notes = _notesController.text.trim();
    if (rating == null || status == null || reason.isEmpty) {
      _snack('Escolha nota, status e motivo.');
      return;
    }
    final previousClips = List<CandidateClip>.from(_clips);
    final previousClip = _clip;
    final previousSummary = _summary;
    final previousRating = _rating;
    final previousStatus = _status;
    final previousReason = _reason;
    final previousNotes = _notesController.text;
    final previousIndex = _clips.indexOf(clip);
    if (previousIndex < 0) return;
    final updatedReview = CandidateReview(
      status: status,
      rating: rating,
      reason: reason,
      notes: notes,
    );
    final updatedClip = clip.copyWith(
      alreadyReviewed: true,
      currentReview: updatedReview,
    );

    _debugSave(
      clip: clip,
      status: status,
      previousIndex: previousIndex,
      beforeLength: previousClips.length,
    );

    setState(() {
      _saving = true;
      _error = null;
      if (_filter == CandidateFilter.pending) {
        _clips = List<CandidateClip>.from(_clips)..removeAt(previousIndex);
        _clip = _nextAfterRemoval(_clips, previousIndex);
        _summary = _optimisticSummaryAfterSave(_summary, status);
      } else {
        _clips = List<CandidateClip>.from(_clips);
        _clips[previousIndex] = updatedClip;
        _clip = _nextAfterKeep(_clips, previousIndex);
      }
      _fillForm(_clip);
    });

    _debugAdvance(
      previousIndex: previousIndex,
      newIndex: _clip == null ? -1 : _clips.indexOf(_clip!),
      afterLength: _clips.length,
    );

    try {
      final result = await _api.saveCandidateReview(
        candidateId: clip.candidateId,
        status: status,
        rating: rating,
        reason: reason,
        notes: notes,
      );
      if (!mounted) return;
      setState(() => _saving = false);
      _refreshSummaryInBackground();
      if (status == 'approved') {
        _refreshGenerationStatusInBackground();
        _snack(
          result.autoGenerationMessage.isNotEmpty
              ? result.autoGenerationMessage
              : 'Aprovado. Gerando corte final em segundo plano.',
        );
      } else if (status == 'needs_adjustment') {
        _snack('Marcado para ajuste.');
      } else {
        _snack('Candidato rejeitado.');
      }
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _clips = previousClips;
        _clip = previousClip;
        _summary = previousSummary;
        _rating = previousRating;
        _status = previousStatus;
        _reason = previousReason;
        _notesController.text = previousNotes;
        _error = error.toString();
        _saving = false;
      });
      _snack('Não foi possível salvar. Tente novamente.');
    }
  }

  CandidateClip? _nextAfterRemoval(
    List<CandidateClip> clips,
    int previousIndex,
  ) {
    if (clips.isEmpty) return null;
    final nextIndex = previousIndex.clamp(0, clips.length - 1);
    return clips[nextIndex];
  }

  CandidateClip? _nextAfterKeep(List<CandidateClip> clips, int previousIndex) {
    if (clips.isEmpty) return null;
    if (clips.length == 1) return clips.first;
    return clips[(previousIndex + 1) % clips.length];
  }

  CandidateSummary? _optimisticSummaryAfterSave(
    CandidateSummary? summary,
    String status,
  ) {
    if (summary == null) return null;
    return CandidateSummary(
      totalCandidates: summary.totalCandidates,
      previewReady: summary.previewReady,
      missingPreview: summary.missingPreview,
      reviewed: summary.reviewed + 1,
      pending: summary.pending > 0 ? summary.pending - 1 : 0,
      approved: summary.approved + (status == 'approved' ? 1 : 0),
      rejected: summary.rejected + (status == 'rejected' ? 1 : 0),
      needsAdjustment:
          summary.needsAdjustment + (status == 'needs_adjustment' ? 1 : 0),
      averageRating: summary.averageRating,
    );
  }

  Future<void> _refreshSummaryInBackground() async {
    try {
      final summary = await _api.fetchCandidateSummary();
      if (!mounted) return;
      setState(() => _summary = summary);
    } catch (_) {}
  }

  Future<void> _refreshGenerationStatusInBackground() async {
    try {
      final status = await _api.fetchApprovedGenerationStatus();
      if (!mounted) return;
      setState(() => _generationStatus = status);
    } catch (_) {}
  }

  void _debugSave({
    required CandidateClip clip,
    required String status,
    required int previousIndex,
    required int beforeLength,
  }) {
    debugPrint(
      '[CandidateSave] candidate_id=${clip.candidateId} status=$status '
      'previous_index=$previousIndex before_length=$beforeLength',
    );
  }

  void _debugAdvance({
    required int previousIndex,
    required int newIndex,
    required int afterLength,
  }) {
    debugPrint(
      '[CandidateSave] previous_index=$previousIndex new_index=$newIndex '
      'after_length=$afterLength',
    );
  }

  Future<void> _startFinalPipeline() async {
    if (_startingFinals) return;
    setState(() => _startingFinals = true);
    try {
      final run = await _api.startOpsJob(
        jobKey: 'pipeline_ready_to_post',
        params: const {
          'download_missing': true,
          'overwrite': true,
          'package_name': 'latest',
        },
      );
      if (!mounted) return;
      setState(() => _startingFinals = false);
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) =>
              ProcessingScreen(initialRun: run, onOpenCandidates: _load),
        ),
      );
      widget.onOpenPosts?.call();
      _load();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _startingFinals = false;
      });
    }
  }

  Future<void> _renderMissingPreviews() async {
    try {
      final run = await _api.startOpsJob(
        jobKey: 'render_candidate_previews',
        params: const {
          'only_missing': true,
          'download_missing': true,
          'overwrite': true,
          'max_missing': 10,
        },
      );
      if (!mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) =>
              ProcessingScreen(initialRun: run, onOpenCandidates: _load),
        ),
      );
      _load();
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    }
  }

  Future<void> _searchMoreContent() async {
    try {
      final run = await _api.startOpsJob(
        jobKey: 'find_videos_flow',
        params: const {
          'max_videos': 3,
          'max_previews': 10,
          'include_diagnostics': false,
          'download_missing': true,
          'overwrite': true,
        },
      );
      if (!mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) =>
              ProcessingScreen(initialRun: run, onOpenCandidates: _load),
        ),
      );
      _load();
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    }
  }

  Future<void> _quickApprove() async {
    if (_saving) return;
    setState(() {
      _status = 'approved';
      _rating = 5;
      _reason = 'perfeito';
    });
    await _saveAndNext();
  }

  Future<void> _showRejectReasons({bool adjustmentOnly = false}) async {
    if (_saving) return;
    final options = adjustmentOnly ? _adjustmentReasons : _rejectReasons;
    final selected = await showModalBottomSheet<_ReviewDecision>(
      context: context,
      backgroundColor: AppColors.surface,
      showDragHandle: true,
      builder: (context) => _ReasonBottomSheet(
        title: adjustmentOnly
            ? 'O que precisa ajustar?'
            : 'Por que negar este corte?',
        options: options,
      ),
    );
    if (selected == null || !mounted) return;
    setState(() {
      _status = selected.status;
      _rating = selected.status == 'needs_adjustment' ? 3 : 2;
      _reason = selected.reason;
    });
    await _saveAndNext();
  }

  Future<void> _showApproveSheet() async {
    if (_saving) return;
    var rating = 5;
    var reason = 'perfeito';
    final approved = await showModalBottomSheet<bool>(
      context: context,
      backgroundColor: AppColors.surface,
      showDragHandle: true,
      builder: (context) => StatefulBuilder(
        builder: (context, setSheetState) => Padding(
          padding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Aprovar corte',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 14),
              RatingStars(
                value: rating,
                onChanged: (value) => setSheetState(() => rating = value),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final item in _approvalReasons)
                    ChoiceChip(
                      selected: reason == item,
                      label: Text(item),
                      onSelected: (_) => setSheetState(() => reason = item),
                    ),
                ],
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                height: 50,
                child: FilledButton.icon(
                  onPressed: () => Navigator.of(context).pop(true),
                  icon: const Icon(Icons.thumb_up_alt_rounded),
                  label: const Text('Aprovar e próximo'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
    if (approved != true || !mounted) return;
    setState(() {
      _status = 'approved';
      _rating = rating;
      _reason = reason;
    });
    await _saveAndNext();
  }

  void _snack(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Column(children: [Expanded(child: _body())]),
      ),
    );
  }

  Widget _body() {
    if (_loading) {
      return const DfLoadingState(message: 'Carregando candidatos...');
    }
    if (_error != null && _clips.isEmpty) {
      return DfErrorState(message: _error!, onRetry: _load);
    }
    final clip = _clip;
    if (clip == null) {
      final concluded =
          _filter == CandidateFilter.pending && (_summary?.reviewed ?? 0) > 0;
      return _CandidateEmptyState(
        concluded: concluded,
        summary: _summary,
        generationStatus: _generationStatus,
        evaluableCount: _clips.length,
        startingFinals: _startingFinals,
        onRefresh: _load,
        onSearchMore: _searchMoreContent,
        onOpenHome: widget.onOpenHome,
        onOpenPosts: widget.onOpenPosts,
        onRenderPreviews: (_summary?.missingPreview ?? 0) > 0
            ? _renderMissingPreviews
            : null,
        onGenerateFinals: _startFinalPipeline,
      );
    }
    return GestureDetector(
      onHorizontalDragEnd: (details) {
        if (_saving) return;
        final velocity = details.primaryVelocity ?? 0;
        if (velocity > 250) {
          _quickApprove();
        } else if (velocity < -250) {
          _showRejectReasons();
        }
      },
      child: Stack(
        fit: StackFit.expand,
        children: [
          Center(
            child:
                clip.previewInvalid ||
                    clip.previewMissing ||
                    !clip.previewExists
                ? const _MissingPreviewCard()
                : ClipVideoPlayer(
                    url: _api.candidatePreviewUrl(clip.outputPreviewFilename),
                    aspectRatio: 9 / 16,
                  ),
          ),
          const _Vignette(),
          Positioned(
            top: 12,
            left: 12,
            right: 12,
            child: _TopMetrics(
              summary: _summary,
              evaluableCount: _clips.length,
              onRefresh: _load,
              saving: _saving,
            ),
          ),
          if (_error != null)
            Positioned(
              top: 86,
              left: 12,
              right: 12,
              child: DfInlineError(message: _error!),
            ),
          Positioned(
            left: 14,
            right: 14,
            bottom: 94,
            child: _ReelsInfoOverlay(
              clip: clip,
              position: _clips.indexOf(clip) + 1,
              total: _clips.length,
            ),
          ),
          Positioned(
            left: 14,
            right: 14,
            bottom: 16,
            child: _ReelsActions(
              saving: _saving,
              onReject: () => _showRejectReasons(),
              onAdjust: () => _showRejectReasons(adjustmentOnly: true),
              onApprove: _quickApprove,
              onApproveDetailed: _showApproveSheet,
            ),
          ),
        ],
      ),
    );
  }
}

class _TopMetrics extends StatelessWidget {
  const _TopMetrics({
    required this.summary,
    required this.evaluableCount,
    required this.onRefresh,
    required this.saving,
  });

  final CandidateSummary? summary;
  final int evaluableCount;
  final VoidCallback onRefresh;
  final bool saving;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        _MiniMetric(label: 'Para avaliar', value: '$evaluableCount'),
        const SizedBox(width: 8),
        _MiniMetric(label: 'Revisados', value: '${summary?.reviewed ?? 0}'),
        const SizedBox(width: 8),
        _MiniMetric(
          label: 'Sem preview',
          value: '${summary?.missingPreview ?? 0}',
        ),
        const Spacer(),
        IconButton.filledTonal(
          onPressed: saving ? null : onRefresh,
          icon: const Icon(Icons.refresh_rounded),
        ),
      ],
    );
  }
}

class _MiniMetric extends StatelessWidget {
  const _MiniMetric({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.black.withValues(alpha: 0.48),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w900),
            ),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppColors.secondaryText,
                fontSize: 10,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ReelsInfoOverlay extends StatelessWidget {
  const _ReelsInfoOverlay({
    required this.clip,
    required this.position,
    required this.total,
  });

  final CandidateClip clip;
  final int position;
  final int total;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          clip.videoTitle,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w900,
            shadows: [Shadow(color: Colors.black, blurRadius: 8)],
          ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 7,
          runSpacing: 7,
          children: [
            DfStatusChip(label: '$position/$total'),
            DfStatusChip(label: 'rank ${clip.rank ?? '-'}'),
            DfStatusChip(label: clip.timeRange),
            DfStatusChip(label: clip.sourceCollection),
            if (clip.reason.isNotEmpty) DfStatusChip(label: clip.reason),
          ],
        ),
        const SizedBox(height: 8),
        const Text(
          'Swipe direita aprova · Swipe esquerda rejeita',
          style: TextStyle(color: AppColors.secondaryText, fontSize: 12),
        ),
      ],
    );
  }
}

class _ReelsActions extends StatelessWidget {
  const _ReelsActions({
    required this.saving,
    required this.onReject,
    required this.onAdjust,
    required this.onApprove,
    required this.onApproveDetailed,
  });

  final bool saving;
  final VoidCallback onReject;
  final VoidCallback onAdjust;
  final VoidCallback onApprove;
  final VoidCallback onApproveDetailed;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _RoundAction(
            label: 'Rejeitar',
            icon: Icons.close_rounded,
            color: AppColors.danger,
            onTap: saving ? null : onReject,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: _RoundAction(
            label: 'Ajustar',
            icon: Icons.tune_rounded,
            color: AppColors.warning,
            onTap: saving ? null : onAdjust,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: GestureDetector(
            onLongPress: saving ? null : onApproveDetailed,
            child: _RoundAction(
              label: saving ? 'Salvando...' : 'Aprovar',
              icon: Icons.favorite_rounded,
              color: AppColors.success,
              onTap: saving ? null : onApprove,
            ),
          ),
        ),
      ],
    );
  }
}

class _RoundAction extends StatelessWidget {
  const _RoundAction({
    required this.label,
    required this.icon,
    required this.color,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: Container(
        height: 64,
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.16),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: color.withValues(alpha: 0.5)),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: color),
            const SizedBox(height: 4),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: color, fontWeight: FontWeight.w900),
            ),
          ],
        ),
      ),
    );
  }
}

class _Vignette extends StatelessWidget {
  const _Vignette();

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Colors.black.withValues(alpha: 0.58),
              Colors.transparent,
              Colors.black.withValues(alpha: 0.78),
            ],
            stops: const [0, 0.42, 1],
          ),
        ),
      ),
    );
  }
}

class _ReviewDecision {
  const _ReviewDecision({required this.reason, required this.status});

  final String reason;
  final String status;
}

const _rejectReasons = [
  _ReviewDecision(reason: 'nao_prende', status: 'rejected'),
  _ReviewDecision(reason: 'sem_contexto', status: 'rejected'),
  _ReviewDecision(reason: 'video_fraco', status: 'rejected'),
  _ReviewDecision(reason: 'corte_ruim', status: 'needs_adjustment'),
  _ReviewDecision(reason: 'comeca_mal', status: 'needs_adjustment'),
  _ReviewDecision(reason: 'termina_mal', status: 'needs_adjustment'),
  _ReviewDecision(reason: 'audio_ruim', status: 'needs_adjustment'),
  _ReviewDecision(reason: 'risco_copyright', status: 'needs_adjustment'),
  _ReviewDecision(reason: 'outro', status: 'rejected'),
];

const _adjustmentReasons = [
  _ReviewDecision(reason: 'corte_comeca_mal', status: 'needs_adjustment'),
  _ReviewDecision(reason: 'corte_termina_mal', status: 'needs_adjustment'),
  _ReviewDecision(reason: 'sem_contexto', status: 'needs_adjustment'),
  _ReviewDecision(reason: 'audio_ruim', status: 'needs_adjustment'),
  _ReviewDecision(reason: 'risco_copyright', status: 'needs_adjustment'),
  _ReviewDecision(reason: 'outro', status: 'needs_adjustment'),
];

const _approvalReasons = [
  'perfeito',
  'bom_gancho',
  'viral',
  'polemico',
  'engracado',
  'forte',
];

class _ReasonBottomSheet extends StatelessWidget {
  const _ReasonBottomSheet({required this.title, required this.options});

  final String title;
  final List<_ReviewDecision> options;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final option in options)
                ActionChip(
                  label: Text(_labelForReason(option.reason)),
                  onPressed: () => Navigator.of(context).pop(option),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

String _labelForReason(String value) {
  return switch (value) {
    'nao_prende' => 'Não prende',
    'sem_contexto' => 'Sem contexto',
    'video_fraco' => 'Vídeo fraco',
    'corte_ruim' => 'Corte ruim',
    'comeca_mal' || 'corte_comeca_mal' => 'Começa mal',
    'termina_mal' || 'corte_termina_mal' => 'Termina mal',
    'audio_ruim' => 'Áudio ruim',
    'risco_copyright' => 'Risco copyright',
    _ => 'Outro',
  };
}

class _MissingPreviewCard extends StatelessWidget {
  const _MissingPreviewCard();

  @override
  Widget build(BuildContext context) {
    return const DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.video_file_outlined, color: AppColors.warning),
          SizedBox(height: 10),
          Text(
            'Preview ainda não renderizado',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
          ),
          SizedBox(height: 6),
          Text(
            'Preview inválido ou ainda não renderizado. Gere o preview novamente em Operations.',
          ),
        ],
      ),
    );
  }
}

class _CandidateEmptyState extends StatelessWidget {
  const _CandidateEmptyState({
    required this.concluded,
    required this.summary,
    required this.generationStatus,
    required this.evaluableCount,
    required this.startingFinals,
    required this.onRefresh,
    required this.onSearchMore,
    required this.onOpenHome,
    required this.onOpenPosts,
    required this.onRenderPreviews,
    required this.onGenerateFinals,
  });

  final bool concluded;
  final CandidateSummary? summary;
  final ApprovedGenerationStatus? generationStatus;
  final int evaluableCount;
  final bool startingFinals;
  final VoidCallback onRefresh;
  final VoidCallback onSearchMore;
  final VoidCallback? onOpenHome;
  final VoidCallback? onOpenPosts;
  final VoidCallback? onRenderPreviews;
  final VoidCallback onGenerateFinals;

  @override
  Widget build(BuildContext context) {
    final approved = summary?.approved ?? 0;
    final generationRunning =
        generationStatus?.running == true ||
        (generationStatus?.pendingCount ?? 0) > 0;
    final generationMessage = generationRunning
        ? '\nSeus cortes aprovados estão sendo gerados em segundo plano.'
        : '';
    return Center(
      child: ListView(
        shrinkWrap: true,
        padding: const EdgeInsets.all(24),
        children: [
          Icon(Icons.travel_explore_rounded, color: AppColors.cyan, size: 48),
          const SizedBox(height: 14),
          const Text(
            'Nenhum candidato pronto para avaliar',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 8),
          Text(
            'Você já avaliou todos os cortes com preview disponível. Busque novos conteúdos ou gere previews faltantes.$generationMessage\n\nPara avaliar: $evaluableCount · revisados: ${summary?.reviewed ?? 0} · sem preview: ${summary?.missingPreview ?? 0}',
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppColors.secondaryText),
          ),
          const SizedBox(height: 18),
          DFPrimaryButton(
            label: 'Buscar mais conteúdo',
            icon: Icons.radar_rounded,
            onPressed: onSearchMore,
          ),
          const SizedBox(height: 10),
          if (concluded && approved > 0 && !generationRunning) ...[
            DFSecondaryButton(
              label: startingFinals ? 'Iniciando...' : 'Gerar finais pendentes',
              icon: Icons.rocket_launch_rounded,
              onPressed: startingFinals ? null : onGenerateFinals,
            ),
          ],
          if (onRenderPreviews != null) ...[
            const SizedBox(height: 10),
            DFSecondaryButton(
              label: 'Renderizar previews faltantes',
              icon: Icons.movie_creation_rounded,
              onPressed: onRenderPreviews,
            ),
          ],
          if (onOpenPosts != null) ...[
            const SizedBox(height: 10),
            DFSecondaryButton(
              label: 'Ir para Posts',
              icon: Icons.publish_rounded,
              onPressed: onOpenPosts,
            ),
          ],
          if (onOpenHome != null) ...[
            const SizedBox(height: 10),
            DFGhostButton(
              label: 'Voltar para Início',
              icon: Icons.home_rounded,
              onPressed: onOpenHome,
            ),
          ],
          const SizedBox(height: 10),
          DFGhostButton(
            label: 'Atualizar',
            icon: Icons.refresh_rounded,
            onPressed: onRefresh,
          ),
        ],
      ),
    );
  }
}
