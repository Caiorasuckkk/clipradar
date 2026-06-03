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
  });

  final JobRun initialRun;
  final VoidCallback onOpenCandidates;

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

  @override
  void initState() {
    super.initState();
    if (_run.isRunning) {
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
      if (!run.isRunning) {
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

  @override
  Widget build(BuildContext context) {
    final success = _run.status == 'success';
    final failed = _run.status == 'failed';
    final readyDespiteFailure = failed && _hasReadyCandidates;
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
                  color: readyDespiteFailure
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
                  ? 'Análise concluída'
                  : readyDespiteFailure
                  ? 'Candidatos encontrados'
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
                    title: 'Gerando candidatos',
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
            if (success || readyDespiteFailure)
              _SuccessActions(
                summary: _candidateSummary,
                readyCandidateCount: _readyCandidateCount,
                loading: _loadingSummary,
                partialWarning: readyDespiteFailure,
                onOpenCandidates: () {
                  Navigator.of(context).pop();
                  widget.onOpenCandidates();
                },
                onRenderPreviews: _startPreviewRender,
                onRetryAnalysis: () => Navigator.of(context).pop(),
              )
            else if (failed)
              DFSecondaryButton(
                label: 'Tentar atualizar',
                icon: Icons.refresh_rounded,
                onPressed: _refresh,
              ),
          ],
        ),
      ),
    );
  }

  bool _stepDone(int step) {
    if (_run.status == 'success') {
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
    if (_run.status == 'success') {
      return 'Previews prontos para revisão.';
    }
    if (_run.status == 'failed') {
      if (_hasReadyCandidates) {
        return 'A análise encontrou candidatos, mas uma etapa auxiliar falhou. Você já pode avaliar os candidatos disponíveis.';
      }
      return 'Confira os logs para entender a falha.';
    }
    if (stdout.contains('Step 5/5')) {
      return 'Renderizando previews para o app.';
    }
    if (stdout.contains('Step 4/5')) {
      return 'Montando a fila de candidatos.';
    }
    if (stdout.contains('Step 3/5')) {
      return 'Processando vídeos selecionados.';
    }
    if (stdout.contains('Step 2/5')) {
      return 'Selecionando os melhores vídeos.';
    }
    return 'Buscando oportunidades com potencial de corte.';
  }
}

class _SuccessActions extends StatelessWidget {
  const _SuccessActions({
    required this.summary,
    required this.readyCandidateCount,
    required this.loading,
    required this.partialWarning,
    required this.onOpenCandidates,
    required this.onRenderPreviews,
    required this.onRetryAnalysis,
  });

  final CandidateSummary? summary;
  final int readyCandidateCount;
  final bool loading;
  final bool partialWarning;
  final VoidCallback onOpenCandidates;
  final VoidCallback onRenderPreviews;
  final VoidCallback onRetryAnalysis;

  @override
  Widget build(BuildContext context) {
    if (loading || summary == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (readyCandidateCount > 0) {
      return Column(
        children: [
          if (partialWarning) ...[
            const Text(
              'A análise encontrou candidatos, mas uma etapa auxiliar falhou. Você já pode avaliar os candidatos disponíveis.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.warning),
            ),
            const SizedBox(height: 12),
          ],
          DFPrimaryButton(
            label: 'Avaliar candidatos agora',
            icon: Icons.swipe_rounded,
            onPressed: onOpenCandidates,
          ),
        ],
      );
    }
    if (summary!.pending > 0 &&
        (summary!.previewReady == 0 || summary!.missingPreview > 0)) {
      return Column(
        children: [
          const Text(
            'Candidatos encontrados, mas os previews ainda precisam ser gerados.',
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
            'Todos os candidatos desta rodada já foram avaliados.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.secondaryText),
          ),
          const SizedBox(height: 12),
          DFSecondaryButton(
            label: 'Ver revisados',
            icon: Icons.fact_check_rounded,
            onPressed: onOpenCandidates,
          ),
        ],
      );
    }
    return Column(
      children: [
        Text(
          summary!.missingPreview > 0
              ? 'Nenhum candidato pronto encontrado. Você pode gerar previews faltantes ou tentar novamente.'
              : 'Nenhum candidato pronto encontrado. Tentar novamente.',
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
