import 'dart:async';

import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../models/candidate_clip.dart';
import '../models/candidate_summary.dart';
import '../models/job_run.dart';
import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import '../widgets/df_button.dart';
import '../widgets/df_card.dart';
import '../widgets/df_status_chip.dart';

class ProcessingScreen extends StatefulWidget {
  const ProcessingScreen({
    super.key,
    required this.initialRun,
    required this.onOpenCandidates,
    this.onOpenHome,
    this.onOpenPosts,
    this.onOpenReviewed,
  });

  final JobRun initialRun;
  final VoidCallback onOpenCandidates;
  final VoidCallback? onOpenHome;
  final VoidCallback? onOpenPosts;
  final VoidCallback? onOpenReviewed;

  @override
  State<ProcessingScreen> createState() => _ProcessingScreenState();
}

class _ProcessingScreenState extends State<ProcessingScreen> {
  final ApiClient _api = ApiClient();
  Timer? _timer;
  late JobRun _run = widget.initialRun;
  CandidateSummary? _candidateSummary;
  int _readyCandidateCount = 0;
  String? _error;
  bool _showLogs = false;
  bool _loadingSummary = false;
  late DateTime _screenStartedAt;
  bool _timeoutNoticeDismissed = false;

  bool get _isTerminalStatus => {
    'success',
    'failed',
    'cancelled',
    'success_with_warnings',
  }.contains(_run.status);

  bool get _isTakingLong =>
      !_isTerminalStatus &&
      !_timeoutNoticeDismissed &&
      DateTime.now().difference(_screenStartedAt).inSeconds >= 180;

  @override
  void initState() {
    super.initState();
    _screenStartedAt = DateTime.now();
    if (!_isTerminalStatus && _run.isRunning) {
      _startPolling();
    } else {
      _loadCandidateSummary();
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _startPolling() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 2), (_) => _refresh());
  }

  Future<void> _refresh() async {
    try {
      final run = await _api.fetchOpsJobRun(_run.runId);
      if (!mounted) {
        return;
      }
      setState(() {
        _run = run;
        _error = null;
      });
      if (run.jobKey == 'find_videos_flow' &&
          (run.isRunning ||
              run.partialReviewable ||
              run.partialPendingReviewableCount > 0)) {
        await _loadCandidateSummary();
      }
      if (_isTerminalStatus || !run.isRunning) {
        _timer?.cancel();
        _loadCandidateSummary();
      }
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _error = error.toString());
    }
  }

  Future<void> _loadCandidateSummary() async {
    if (_loadingSummary) return;
    setState(() => _loadingSummary = true);
    try {
      final summary = await _api.fetchCandidateSummary();
      final clips = await _api.fetchCandidateClips(status: 'pending');
      if (!mounted) return;
      setState(() {
        _candidateSummary = summary;
        _readyCandidateCount = _evaluableClips(clips).length;
        _loadingSummary = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _loadingSummary = false;
      });
    }
  }

  Future<void> _startPreviewRender() async {
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
      setState(() {
        _run = run;
        _candidateSummary = null;
        _readyCandidateCount = 0;
        _error = null;
      });
      _startPolling();
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    }
  }

  Future<void> _cancelJob() async {
    try {
      await _api.cancelOpsJobRun(_run.runId);
      if (!mounted) return;
      setState(() {
        _timeoutNoticeDismissed = true;
        _error = 'Job cancelado.';
      });
      await _refresh();
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    }
  }

  Future<void> _showFullStatus() async {
    JobRunLogs? logs;
    Object? loadError;
    try {
      logs = await _api.fetchOpsJobRunLogs(_run.runId);
    } catch (error) {
      loadError = error;
    }
    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: AppColors.surface,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (context) =>
          _FullStatusSheet(run: _run, logs: logs, error: loadError?.toString()),
    );
  }

  Future<void> _openCandidatesIfAvailable() async {
    setState(() => _loadingSummary = true);
    try {
      final clips = await _api.fetchCandidateClips(status: 'pending');
      final summary = await _api.fetchCandidateSummary();
      final readyCount = _evaluableClips(clips).length;
      if (!mounted) return;
      if (readyCount == 0) {
        setState(() {
          _candidateSummary = summary;
          _readyCandidateCount = 0;
          _loadingSummary = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Todos os cortes foram avaliados.')),
        );
        return;
      }
      setState(() {
        _candidateSummary = summary;
        _readyCandidateCount = readyCount;
        _loadingSummary = false;
      });
      Navigator.of(context).pop();
      widget.onOpenCandidates();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _loadingSummary = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final success =
        _run.status == 'success' || _run.status == 'success_with_warnings';
    final successWarning = _run.status == 'success_with_warnings';
    final failed = _run.status == 'failed';
    final backendReadyHint =
        _candidateSummary == null && _run.pendingReviewableCount > 0;
    final readyDespiteFailure =
        failed && (_hasReadyCandidates || backendReadyHint);
    final hasPartialReady =
        _run.partialReviewable ||
        _run.partialPendingReviewableCount > 0 ||
        (_run.isRunning && _hasReadyCandidates);
    final partialWarning = successWarning || readyDespiteFailure;
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(18),
          children: [
            Row(
              children: [
                IconButton(
                  onPressed: () => Navigator.of(context).maybePop(),
                  icon: const Icon(Icons.arrow_back_rounded),
                ),
                const Expanded(
                  child: Text('Processamento', style: AppTextStyles.section),
                ),
                DfStatusChip(label: _run.status, status: _run.status),
              ],
            ),
            const SizedBox(height: 22),
            Center(
              child: Container(
                width: 112,
                height: 112,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: AppColors.cyan.withValues(alpha: 0.12),
                  border: Border.all(
                    color: AppColors.cyan.withValues(alpha: 0.35),
                  ),
                ),
                child: Icon(
                  failed
                      ? Icons.error_outline_rounded
                      : success
                      ? Icons.check_rounded
                      : Icons.radar_rounded,
                  color: partialWarning
                      ? AppColors.warning
                      : failed
                      ? AppColors.danger
                      : AppColors.cyan,
                  size: 54,
                ),
              ),
            ),
            const SizedBox(height: 18),
            Text(
              success
                  ? successWarning
                        ? 'Cortes encontrados'
                        : 'Análise concluída'
                  : readyDespiteFailure
                  ? 'Cortes encontrados'
                  : failed
                  ? 'Job falhou'
                  : 'Analisando vídeos',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 8),
            Text(
              _stageLabel(_run.stdoutTail),
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.secondaryText),
            ),
            if (_candidateSummary != null &&
                (_isTerminalStatus || hasPartialReady)) ...[
              const SizedBox(height: 12),
              _ProcessingSummaryCard(
                summary: _candidateSummary!,
                readyCount: _readyCandidateCount,
              ),
            ],
            if (_run.isRunning &&
                (_run.currentVideoId.isNotEmpty ||
                    _run.currentVideoIndex != null)) ...[
              const SizedBox(height: 12),
              _ProgressDetailCard(run: _run),
            ],
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(
                _error!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.danger),
              ),
            ],
            const SizedBox(height: 24),
            DfCard(
              child: Column(
                children: [
                  _StepRow(
                    title: 'Descobrindo vídeos',
                    done: _stepDone(1),
                    active: _stepActive(1),
                  ),
                  _StepRow(
                    title: 'Selecionando melhores',
                    done: _stepDone(2),
                    active: _stepActive(2),
                  ),
                  _StepRow(
                    title: 'Processando vídeos',
                    done: _stepDone(3),
                    active: _stepActive(3),
                  ),
                  _StepRow(
                    title: 'Gerando cortes',
                    done: _stepDone(4),
                    active: _stepActive(4),
                  ),
                  _StepRow(
                    title: 'Renderizando previews',
                    done: _stepDone(5),
                    active: _stepActive(5),
                    last: true,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            DfCard(
              padding: EdgeInsets.zero,
              child: ExpansionTile(
                title: const Text('Logs recentes'),
                initiallyExpanded: _showLogs,
                onExpansionChanged: (value) =>
                    setState(() => _showLogs = value),
                childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
                children: [
                  Container(
                    width: double.infinity,
                    constraints: const BoxConstraints(maxHeight: 220),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.black,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: SingleChildScrollView(
                      child: Text(
                        _run.stdoutTail.isEmpty
                            ? 'Sem logs ainda.'
                            : _run.stdoutTail,
                        style: const TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),
            if (_isTakingLong) ...[
              _LongRunningNotice(
                onShowStatus: _showFullStatus,
                onRefresh: _refresh,
                onCancel: _cancelJob,
                onBackHome: () => Navigator.of(context).pop(),
              ),
              const SizedBox(height: 18),
            ],
            if (success || readyDespiteFailure || hasPartialReady)
              _SuccessActions(
                summary: _candidateSummary,
                readyCandidateCount: _readyCandidateCount,
                loading: _loadingSummary,
                partialWarning: partialWarning || hasPartialReady,
                runningPartial: _run.isRunning && hasPartialReady,
                onOpenCandidates: _openCandidatesIfAvailable,
                onRenderPreviews: _startPreviewRender,
                onShowStatus: _showFullStatus,
                onRetryAnalysis: () => Navigator.of(context).pop(),
                onOpenHome: widget.onOpenHome == null
                    ? null
                    : () {
                        Navigator.of(context).pop();
                        widget.onOpenHome!.call();
                      },
                onOpenPosts: widget.onOpenPosts == null
                    ? null
                    : () {
                        Navigator.of(context).pop();
                        widget.onOpenPosts!.call();
                      },
                onOpenReviewed: () {
                  Navigator.of(context).pop();
                  (widget.onOpenReviewed ?? widget.onOpenCandidates).call();
                },
              )
            else if (failed && _loadingSummary)
              const _VerifyingCandidateActions()
            else if (failed)
              _FailedActions(
                latestError: _friendlyLatestError,
                onShowStatus: _showFullStatus,
                onRefresh: _refresh,
                onRetry: () => Navigator.of(context).pop(),
                onBackHome: () {
                  Navigator.of(context).pop();
                  widget.onOpenHome?.call();
                },
              ),
          ],
        ),
      ),
    );
  }

  bool _stepDone(int step) {
    if (_run.status == 'success' || _run.status == 'success_with_warnings') {
      return true;
    }
    final current = _currentStep(_run.stdoutTail);
    return current > step;
  }

  bool get _hasReadyCandidates {
    return _readyCandidateCount > 0;
  }

  List<CandidateClip> _evaluableClips(List<CandidateClip> clips) {
    return clips.where((clip) {
      final reviewed =
          clip.alreadyReviewed ||
          {
            'approved',
            'rejected',
            'needs_adjustment',
          }.contains(clip.currentReview?.status);
      return !reviewed &&
          clip.previewExists &&
          !clip.previewMissing &&
          !clip.previewInvalid;
    }).toList();
  }

  bool _stepActive(int step) {
    if (!_run.isRunning) {
      return false;
    }
    return _currentStep(_run.stdoutTail) == step;
  }

  int _currentStep(String stdout) {
    for (var step = 5; step >= 1; step--) {
      if (stdout.contains('Step $step/5')) {
        return step;
      }
    }
    return _run.isRunning ? 1 : 0;
  }

  String _stageLabel(String stdout) {
    if (_run.status == 'success' || _run.status == 'success_with_warnings') {
      if (_run.status == 'success_with_warnings') {
        return 'A análise falhou parcialmente, mas há cortes prontos.';
      }
      if (!_run.isRunning &&
          _candidateSummary != null &&
          _readyCandidateCount == 0) {
        if ((_candidateSummary?.pending ?? 0) == 0 &&
            ((_candidateSummary?.reviewed ?? 0) > 0 ||
                ((_candidateSummary?.approved ?? 0) +
                        (_candidateSummary?.rejected ?? 0) +
                        (_candidateSummary?.needsAdjustment ?? 0)) >
                    0)) {
          return 'Todos os cortes desta busca foram avaliados.';
        }
      }
      return 'Previews prontos para revisão.';
    }
    if (_run.status == 'failed') {
      if (_hasReadyCandidates) {
        return 'A análise falhou parcialmente, mas há cortes prontos.';
      }
      return _friendlyLatestError.isNotEmpty
          ? _friendlyLatestError
          : 'Confira os logs para entender a falha.';
    }
    if (_isTakingLong) {
      return 'Esta análise está demorando mais que o normal.';
    }
    if (_run.partialReviewable ||
        _run.partialPendingReviewableCount > 0 ||
        (_run.isRunning && _hasReadyCandidates)) {
      return 'Já encontramos cortes prontos. A busca continuará em segundo plano.';
    }
    if (_run.currentVideoIndex != null && (_run.totalVideos ?? 0) > 0) {
      return 'Processando vídeo ${_run.currentVideoIndex} de ${_run.totalVideos}.';
    }
    if (stdout.contains('Step 5/5')) {
      return 'Renderizando previews para o app.';
    }
    if (stdout.contains('Step 4/5')) {
      return 'Montando a fila de cortes.';
    }
    if (stdout.contains('Step 3/5')) {
      return 'Processando vídeos selecionados.';
    }
    if (stdout.contains('Step 2/5')) {
      return 'Selecionando os melhores vídeos.';
    }
    return 'Buscando oportunidades com potencial de corte.';
  }

  String get _friendlyLatestError {
    final raw = _run.latestError.trim().isNotEmpty
        ? _run.latestError.trim()
        : _run.stderrTail.trim();
    if (raw.contains('process_not_found_stale_run')) {
      return 'O processo de busca foi encerrado antes de finalizar. Veja os logs ou tente novamente.';
    }
    return raw;
  }
}

class _SuccessActions extends StatelessWidget {
  const _SuccessActions({
    required this.summary,
    required this.readyCandidateCount,
    required this.loading,
    required this.partialWarning,
    required this.runningPartial,
    required this.onOpenCandidates,
    required this.onRenderPreviews,
    required this.onShowStatus,
    required this.onRetryAnalysis,
    required this.onOpenHome,
    required this.onOpenPosts,
    required this.onOpenReviewed,
  });

  final CandidateSummary? summary;
  final int readyCandidateCount;
  final bool loading;
  final bool partialWarning;
  final bool runningPartial;
  final VoidCallback onOpenCandidates;
  final VoidCallback onRenderPreviews;
  final VoidCallback onShowStatus;
  final VoidCallback onRetryAnalysis;
  final VoidCallback? onOpenHome;
  final VoidCallback? onOpenPosts;
  final VoidCallback onOpenReviewed;

  @override
  Widget build(BuildContext context) {
    if (loading || summary == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (readyCandidateCount > 0) {
      return Column(
        children: [
          if (runningPartial) ...[
            const Text(
              'Já encontramos cortes prontos. Você pode avaliar agora enquanto a busca termina em segundo plano.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.warning),
            ),
            const SizedBox(height: 12),
          ],
          if (partialWarning && !runningPartial) ...[
            const Text(
              'A análise encontrou cortes antes de finalizar todas as etapas.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.warning),
            ),
            const SizedBox(height: 12),
          ],
          DFPrimaryButton(
            label: 'Avaliar cortes agora',
            icon: Icons.swipe_rounded,
            onPressed: onOpenCandidates,
          ),
          if (summary!.missingPreview > 0) ...[
            const SizedBox(height: 10),
            DFSecondaryButton(
              label: 'Renderizar previews faltantes',
              icon: Icons.movie_creation_rounded,
              onPressed: onRenderPreviews,
            ),
          ],
          if (partialWarning) ...[
            const SizedBox(height: 10),
            DFSecondaryButton(
              label: 'Ver status completo',
              icon: Icons.terminal_rounded,
              onPressed: onShowStatus,
            ),
            const SizedBox(height: 10),
            DFSecondaryButton(
              label: 'Buscar mais conteúdo',
              icon: Icons.radar_rounded,
              onPressed: onRetryAnalysis,
            ),
            if (onOpenHome != null) ...[
              const SizedBox(height: 10),
              DFGhostButton(
                label: 'Voltar ao início',
                icon: Icons.home_rounded,
                onPressed: onOpenHome,
              ),
            ],
          ],
        ],
      );
    }
    if (summary!.pending > 0 &&
        (summary!.previewReady == 0 || summary!.missingPreview > 0)) {
      return Column(
        children: [
          const Text(
            'Cortes encontrados, mas os previews ainda precisam ser gerados.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.secondaryText),
          ),
          const SizedBox(height: 12),
          DFPrimaryButton(
            label: 'Renderizar previews',
            icon: Icons.movie_creation_rounded,
            onPressed: onRenderPreviews,
          ),
        ],
      );
    }
    if (summary!.pending == 0 &&
        (summary!.approved + summary!.rejected + summary!.needsAdjustment) >
            0) {
      return Column(
        children: [
          const Text(
            'Todos os cortes encontrados até agora foram avaliados.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.secondaryText),
          ),
          const SizedBox(height: 12),
          if (onOpenPosts != null) ...[
            DFPrimaryButton(
              label: 'Ir para Cortes > Posts',
              icon: Icons.publish_rounded,
              onPressed: onOpenPosts,
            ),
            const SizedBox(height: 10),
          ],
          DFSecondaryButton(
            label: 'Buscar mais conteúdo',
            icon: Icons.radar_rounded,
            onPressed: onRetryAnalysis,
          ),
          const SizedBox(height: 10),
          DFSecondaryButton(
            label: 'Ver status completo',
            icon: Icons.terminal_rounded,
            onPressed: onShowStatus,
          ),
          if (onOpenHome != null) ...[
            const SizedBox(height: 10),
            DFGhostButton(
              label: 'Voltar ao início',
              icon: Icons.home_rounded,
              onPressed: onOpenHome,
            ),
          ],
        ],
      );
    }
    return Column(
      children: [
        Text(
          summary!.missingPreview > 0
              ? 'Nenhum corte pronto encontrado. Você pode gerar previews faltantes ou tentar novamente.'
              : 'Nenhum corte pronto encontrado. Tentar novamente.',
          textAlign: TextAlign.center,
          style: const TextStyle(color: AppColors.secondaryText),
        ),
        const SizedBox(height: 12),
        DFSecondaryButton(
          label: 'Tentar nova análise',
          icon: Icons.refresh_rounded,
          onPressed: onRetryAnalysis,
        ),
      ],
    );
  }
}

class _ProgressDetailCard extends StatelessWidget {
  const _ProgressDetailCard({required this.run});

  final JobRun run;

  @override
  Widget build(BuildContext context) {
    final index = run.currentVideoIndex;
    final total = run.totalVideos;
    final hasIndex = index != null && total != null && total > 0;
    return DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.movie_filter_rounded, color: AppColors.cyan),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  hasIndex
                      ? 'Processando vídeo $index de $total'
                      : 'Processando vídeo',
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (run.currentVideoId.isNotEmpty)
            Text(
              run.currentVideoId,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.muted,
            ),
          if (run.currentStepDetail.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              run.currentStepDetail.replaceAll('_', ' '),
              style: const TextStyle(color: AppColors.secondaryText),
            ),
          ],
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              DfStatusChip(label: 'cortes ${run.partialCandidateCount}'),
              DfStatusChip(label: 'previews ${run.partialPreviewReady}'),
              DfStatusChip(
                label: 'avaliar ${run.partialPendingReviewableCount}',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ProcessingSummaryCard extends StatelessWidget {
  const _ProcessingSummaryCard({
    required this.summary,
    required this.readyCount,
  });

  final CandidateSummary summary;
  final int readyCount;

  @override
  Widget build(BuildContext context) {
    return DfCard(
      child: Wrap(
        spacing: 14,
        runSpacing: 8,
        alignment: WrapAlignment.center,
        children: [
          _SummaryMetric(
            label: 'Cortes encontrados',
            value: summary.totalCandidates,
          ),
          _SummaryMetric(label: 'Prontos', value: summary.previewReady),
          _SummaryMetric(label: 'Para avaliar', value: readyCount),
          _SummaryMetric(label: 'Sem preview', value: summary.missingPreview),
        ],
      ),
    );
  }
}

class _SummaryMetric extends StatelessWidget {
  const _SummaryMetric({required this.label, required this.value});

  final String label;
  final int value;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          '$value',
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: const TextStyle(color: AppColors.secondaryText, fontSize: 11),
        ),
      ],
    );
  }
}

class _VerifyingCandidateActions extends StatelessWidget {
  const _VerifyingCandidateActions();

  @override
  Widget build(BuildContext context) {
    return const DfCard(
      child: Column(
        children: [
          CircularProgressIndicator(),
          SizedBox(height: 12),
          Text(
            'Verificando cortes prontos antes de mostrar a falha.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.secondaryText),
          ),
        ],
      ),
    );
  }
}

class _LongRunningNotice extends StatelessWidget {
  const _LongRunningNotice({
    required this.onShowStatus,
    required this.onRefresh,
    required this.onCancel,
    required this.onBackHome,
  });

  final VoidCallback onShowStatus;
  final VoidCallback onRefresh;
  final VoidCallback onCancel;
  final VoidCallback onBackHome;

  @override
  Widget build(BuildContext context) {
    return DfCard(
      child: Column(
        children: [
          const Text(
            'Esta análise está demorando mais que o normal.',
            textAlign: TextAlign.center,
            style: TextStyle(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 12),
          DFSecondaryButton(
            label: 'Ver status avançado',
            icon: Icons.terminal_rounded,
            onPressed: onShowStatus,
          ),
          const SizedBox(height: 10),
          DFSecondaryButton(
            label: 'Atualizar',
            icon: Icons.refresh_rounded,
            onPressed: onRefresh,
          ),
          const SizedBox(height: 10),
          DFSecondaryButton(
            label: 'Cancelar job',
            icon: Icons.cancel_rounded,
            onPressed: onCancel,
          ),
          const SizedBox(height: 10),
          DFGhostButton(
            label: 'Voltar ao início',
            icon: Icons.home_rounded,
            onPressed: onBackHome,
          ),
        ],
      ),
    );
  }
}

class _FailedActions extends StatelessWidget {
  const _FailedActions({
    required this.latestError,
    required this.onShowStatus,
    required this.onRefresh,
    required this.onRetry,
    required this.onBackHome,
  });

  final String latestError;
  final VoidCallback onShowStatus;
  final VoidCallback onRefresh;
  final VoidCallback onRetry;
  final VoidCallback onBackHome;

  @override
  Widget build(BuildContext context) {
    return DfCard(
      child: Column(
        children: [
          Text(
            latestError.isEmpty
                ? 'Não foi possível concluir a análise. Veja os logs ou tente novamente.'
                : latestError,
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppColors.secondaryText),
          ),
          const SizedBox(height: 12),
          DFSecondaryButton(
            label: 'Ver status completo',
            icon: Icons.terminal_rounded,
            onPressed: onShowStatus,
          ),
          const SizedBox(height: 10),
          DFSecondaryButton(
            label: 'Tentar atualizar',
            icon: Icons.refresh_rounded,
            onPressed: onRefresh,
          ),
          const SizedBox(height: 10),
          DFPrimaryButton(
            label: 'Buscar mais conteúdo',
            icon: Icons.radar_rounded,
            onPressed: onRetry,
          ),
          const SizedBox(height: 10),
          DFGhostButton(
            label: 'Voltar ao início',
            icon: Icons.home_rounded,
            onPressed: onBackHome,
          ),
        ],
      ),
    );
  }
}

class _FullStatusSheet extends StatelessWidget {
  const _FullStatusSheet({
    required this.run,
    required this.logs,
    required this.error,
  });

  final JobRun run;
  final JobRunLogs? logs;
  final String? error;

  @override
  Widget build(BuildContext context) {
    final stdout = logs?.stdoutTail.isNotEmpty == true
        ? logs!.stdoutTail
        : run.stdoutTail;
    final stderr = logs?.stderrTail.isNotEmpty == true
        ? logs!.stderrTail
        : run.stderrTail;
    final currentStep = _currentInstrumentedStep(stdout);
    final currentStepDuration = _currentInstrumentedStepDuration(stdout);
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Status completo',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 12),
              _StatusLine(label: 'run_id', value: run.runId),
              _StatusLine(
                label: 'job_key',
                value: logs?.jobKey.isNotEmpty == true
                    ? logs!.jobKey
                    : run.jobKey,
              ),
              _StatusLine(
                label: 'status',
                value: logs?.status.isNotEmpty == true
                    ? logs!.status
                    : run.status,
              ),
              _StatusLine(
                label: 'pid',
                value: '${logs?.pid ?? run.pid ?? '-'}',
              ),
              _StatusLine(
                label: 'started_at',
                value: logs?.startedAt.isNotEmpty == true
                    ? logs!.startedAt
                    : run.startedAt,
              ),
              _StatusLine(
                label: 'elapsed_seconds',
                value: '${logs?.elapsedSeconds ?? run.elapsedSeconds ?? '-'}',
              ),
              _StatusLine(
                label: 'current_step',
                value: currentStep.isEmpty ? '-' : currentStep,
              ),
              _StatusLine(
                label: 'current_step_elapsed_seconds',
                value: currentStepDuration == null
                    ? '-'
                    : '$currentStepDuration',
              ),
              _StatusLine(label: 'latest_error', value: run.latestError),
              _StatusLine(label: 'warning_message', value: run.warningMessage),
              _StatusLine(
                label: 'candidate_count',
                value: run.candidateCount == 0 ? '-' : '${run.candidateCount}',
              ),
              _StatusLine(
                label: 'preview_ready',
                value: run.previewReady == 0 ? '-' : '${run.previewReady}',
              ),
              _StatusLine(
                label: 'missing_preview',
                value: run.missingPreview == 0 ? '-' : '${run.missingPreview}',
              ),
              _StatusLine(
                label: 'pending_reviewable_count',
                value: run.pendingReviewableCount == 0
                    ? '-'
                    : '${run.pendingReviewableCount}',
              ),
              _StatusLine(label: 'next_action', value: run.nextAction),
              _StatusLine(
                label: 'command',
                value:
                    (logs?.command.isNotEmpty == true
                            ? logs!.command
                            : run.command)
                        .join(' '),
              ),
              if (error != null && error!.isNotEmpty) ...[
                const SizedBox(height: 10),
                Text(error!, style: const TextStyle(color: AppColors.danger)),
              ],
              const SizedBox(height: 14),
              _LogBlock(title: 'stdout_tail', value: stdout),
              const SizedBox(height: 12),
              _LogBlock(title: 'stderr_tail', value: stderr),
            ],
          ),
        ),
      ),
    );
  }
}

String _currentInstrumentedStep(String stdout) {
  final starts = RegExp(
    r'\[step_start\]\s+step=(\d+)\s+name=([^\s]+)\s+started_at=([^\s]+)',
  ).allMatches(stdout).toList();
  if (starts.isEmpty) return '';
  final ended = RegExp(r'\[step_end\]\s+step=(\d+)')
      .allMatches(stdout)
      .map((match) => match.group(1))
      .whereType<String>()
      .toSet();
  for (final match in starts.reversed) {
    final step = match.group(1) ?? '';
    if (!ended.contains(step)) {
      return '$step ${match.group(2) ?? ''}'.trim();
    }
  }
  final last = starts.last;
  return '${last.group(1) ?? ''} ${last.group(2) ?? ''}'.trim();
}

int? _currentInstrumentedStepDuration(String stdout) {
  final starts = RegExp(
    r'\[step_start\]\s+step=(\d+)\s+name=([^\s]+)\s+started_at=([^\s]+)',
  ).allMatches(stdout).toList();
  if (starts.isEmpty) return null;
  final match = starts.last;
  final started = DateTime.tryParse(match.group(3) ?? '');
  if (started == null) return null;
  return DateTime.now().toUtc().difference(started).inSeconds;
}

class _StatusLine extends StatelessWidget {
  const _StatusLine({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 7),
      child: Text(
        '$label: ${value.isEmpty ? '-' : value}',
        style: const TextStyle(color: AppColors.secondaryText),
      ),
    );
  }
}

class _LogBlock extends StatelessWidget {
  const _LogBlock({required this.title, required this.value});

  final String title;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
        const SizedBox(height: 6),
        Container(
          width: double.infinity,
          constraints: const BoxConstraints(maxHeight: 220),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.black,
            borderRadius: BorderRadius.circular(12),
          ),
          child: SingleChildScrollView(
            child: Text(
              value.trim().isEmpty ? 'Sem logs disponíveis ainda.' : value,
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
            ),
          ),
        ),
      ],
    );
  }
}

class _StepRow extends StatelessWidget {
  const _StepRow({
    required this.title,
    required this.done,
    required this.active,
    this.last = false,
  });

  final String title;
  final bool done;
  final bool active;
  final bool last;

  @override
  Widget build(BuildContext context) {
    final color = done
        ? AppColors.success
        : active
        ? AppColors.cyan
        : AppColors.muted;
    return Padding(
      padding: EdgeInsets.only(bottom: last ? 0 : 12),
      child: Row(
        children: [
          Icon(
            done
                ? Icons.check_circle_rounded
                : active
                ? Icons.radio_button_checked_rounded
                : Icons.radio_button_unchecked_rounded,
            color: color,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              title,
              style: TextStyle(color: color, fontWeight: FontWeight.w800),
            ),
          ),
        ],
      ),
    );
  }
}
