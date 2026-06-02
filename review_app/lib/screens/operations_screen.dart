import 'dart:async';

import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../models/job_run.dart';
import '../models/ops_status.dart';

class OperationsScreen extends StatefulWidget {
  const OperationsScreen({super.key, required this.onOpenCandidates});

  final VoidCallback onOpenCandidates;

  @override
  State<OperationsScreen> createState() => _OperationsScreenState();
}

class _OperationsScreenState extends State<OperationsScreen> {
  final ApiClient _api = ApiClient();
  OpsStatus? _status;
  JobRun? _activeRun;
  Timer? _pollTimer;
  bool _loadingStatus = true;
  bool _starting = false;
  String? _runningJobKey;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadStatus();
    _loadLatestRun();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadStatus() async {
    setState(() {
      _loadingStatus = true;
      _error = null;
    });
    try {
      final status = await _api.fetchOpsStatus();
      if (!mounted) return;
      setState(() {
        _status = status;
        _loadingStatus = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _loadingStatus = false;
      });
    }
  }

  Future<void> _loadLatestRun() async {
    try {
      final run = await _api.fetchLatestOpsRun();
      if (!mounted || run.runId.isEmpty) return;
      setState(() => _activeRun = run);
      if (run.isRunning) _startPolling(run.runId);
    } catch (_) {}
  }

  Future<void> _startJob(_OpAction action) async {
    if (_starting || _activeRun?.isRunning == true) return;
    setState(() {
      _starting = true;
      _runningJobKey = action.jobKey;
      _error = null;
    });
    try {
      final run = await _api.startOpsJob(
        jobKey: action.jobKey,
        params: action.params,
      );
      if (!mounted) return;
      setState(() {
        _activeRun = run;
        _starting = false;
      });
      _startPolling(run.runId);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _starting = false;
        _runningJobKey = null;
      });
    }
  }

  void _startPolling(String runId) {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      try {
        final run = await _api.fetchOpsJobRun(runId);
        if (!mounted) return;
        setState(() => _activeRun = run);
        if (!run.isRunning) {
          _pollTimer?.cancel();
          _runningJobKey = null;
          _loadStatus();
        }
      } catch (error) {
        if (!mounted) return;
        setState(() => _error = error.toString());
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final run = _activeRun;
    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _loadStatus,
          child: ListView(
            padding: const EdgeInsets.all(14),
            children: [
              _Header(onRefresh: _loadStatus, loading: _loadingStatus),
              if (_error != null) ...[
                const SizedBox(height: 10),
                _ErrorCard(message: _error!),
              ],
              const SizedBox(height: 12),
              _StatusGrid(status: _status),
              const SizedBox(height: 14),
              _FindVideosCard(
                disabled: _starting || run?.isRunning == true,
                starting:
                    _runningJobKey == _findVideosAction.jobKey && _starting,
                onStart: () => _startJob(_findVideosAction),
              ),
              if (_canReviewCandidates(run)) ...[
                const SizedBox(height: 10),
                SizedBox(
                  height: 52,
                  child: FilledButton.icon(
                    onPressed: widget.onOpenCandidates,
                    icon: const Icon(Icons.play_circle_fill_rounded),
                    label: const Text('Avaliar candidatos agora'),
                  ),
                ),
              ],
              const SizedBox(height: 14),
              const _BackendNotice(),
              const SizedBox(height: 14),
              const _SectionTitle('Fluxo rápido'),
              _ActionGroup(
                title: '',
                actions: _quickActions,
                starting: _starting,
                runningJobKey: _runningJobKey,
                hasRunningJob: run?.isRunning == true,
                onRun: _startJob,
              ),
              const SizedBox(height: 14),
              const _SectionTitle('Avançado'),
              const SizedBox(height: 8),
              for (final group in _actionGroups) ...[
                _ActionGroup(
                  title: group.title,
                  actions: group.actions,
                  starting: _starting,
                  runningJobKey: _runningJobKey,
                  hasRunningJob: run?.isRunning == true,
                  onRun: _startJob,
                ),
                const SizedBox(height: 14),
              ],
              _RunCard(run: run),
            ],
          ),
        ),
      ),
    );
  }

  bool _canReviewCandidates(JobRun? run) {
    final status = _status;
    return run?.status == 'success' &&
        status != null &&
        status.previewReady > 0 &&
        status.candidateReviewsPending > 0;
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.onRefresh, required this.loading});

  final VoidCallback onRefresh;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Icon(Icons.tune_rounded, color: Color(0xFF00C8F0)),
        const SizedBox(width: 10),
        const Expanded(
          child: Text(
            'Operations',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
          ),
        ),
        IconButton(
          onPressed: loading ? null : onRefresh,
          icon: loading
              ? const SizedBox.square(
                  dimension: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.refresh_rounded),
        ),
      ],
    );
  }
}

class _StatusGrid extends StatelessWidget {
  const _StatusGrid({required this.status});

  final OpsStatus? status;

  @override
  Widget build(BuildContext context) {
    final items = [
      ('Candidates', status?.totalCandidates ?? 0),
      ('Previews ok', status?.previewReady ?? 0),
      ('Previews falta', status?.missingPreview ?? 0),
      ('Cand. pend.', status?.candidateReviewsPending ?? 0),
      ('Cand. ok', status?.candidateApproved ?? 0),
      ('Final pend.', status?.finalReviewsPending ?? 0),
      ('Ready', status?.readyToPost ?? 0),
      ('Fail dl', status?.failedDownloads ?? 0),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: items.length,
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            mainAxisExtent: 92,
            mainAxisSpacing: 10,
            crossAxisSpacing: 10,
          ),
          itemBuilder: (context, index) {
            final item = items[index];
            return _MetricTile(label: item.$1, value: item.$2.toString());
          },
        ),
        const SizedBox(height: 8),
        _MetricTile(
          label: 'Último package',
          value: _packageName(status?.latestPackage ?? ''),
          wide: true,
        ),
      ],
    );
  }
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({
    required this.label,
    required this.value,
    this.wide = false,
  });

  final String label;
  final String value;
  final bool wide;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: BoxConstraints(minHeight: wide ? 78 : 92),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1018),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF242838)),
      ),
      child: Center(
        child: SizedBox(
          width: double.infinity,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 2),
              SizedBox(
                height: 24,
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    value.isEmpty ? '-' : value,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w900,
                    ),
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

class _BackendNotice extends StatelessWidget {
  const _BackendNotice();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF101827),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF1E4058)),
      ),
      child: const Text('Mantenha o backend aberto até o job terminar.'),
    );
  }
}

class _FindVideosCard extends StatelessWidget {
  const _FindVideosCard({
    required this.disabled,
    required this.starting,
    required this.onStart,
  });

  final bool disabled;
  final bool starting;
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF101827),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFF1E4058)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.manage_search_rounded, color: Color(0xFF00C8F0)),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Encontrar vídeos',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Text(
            'Busca novos vídeos e prepara candidatos para você avaliar.',
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            height: 54,
            child: FilledButton.icon(
              onPressed: disabled ? null : onStart,
              icon: starting
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.search_rounded),
              label: Text(starting ? 'Começando...' : 'Começar busca'),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
    );
  }
}

class _ActionGroup extends StatelessWidget {
  const _ActionGroup({
    required this.title,
    required this.actions,
    required this.starting,
    required this.runningJobKey,
    required this.hasRunningJob,
    required this.onRun,
  });

  final String title;
  final List<_OpAction> actions;
  final bool starting;
  final String? runningJobKey;
  final bool hasRunningJob;
  final ValueChanged<_OpAction> onRun;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final action in actions)
              FilledButton.icon(
                onPressed: hasRunningJob || starting
                    ? null
                    : () => onRun(action),
                icon: Icon(action.icon),
                label: Text(
                  runningJobKey == action.jobKey && starting
                      ? 'Iniciando...'
                      : action.label,
                ),
              ),
          ],
        ),
      ],
    );
  }
}

class _RunCard extends StatelessWidget {
  const _RunCard({required this.run});

  final JobRun? run;

  @override
  Widget build(BuildContext context) {
    final current = run;
    if (current == null || current.runId.isEmpty) {
      return const _EmptyRunCard();
    }
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1018),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                current.isRunning
                    ? Icons.hourglass_top_rounded
                    : Icons.check_circle_rounded,
                color: current.status == 'failed'
                    ? const Color(0xFFEF4444)
                    : const Color(0xFF00C8F0),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '${current.jobKey} · ${current.status}',
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (current.jobKey == 'find_videos_flow' && current.isRunning) ...[
            Text(
              _workflowStage(current.stdoutTail),
              style: const TextStyle(
                color: Color(0xFF00C8F0),
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 8),
          ],
          Text('run_id: ${current.runId}'),
          Text(
            'exit: ${current.exitCode ?? '-'} · ${current.elapsedSeconds ?? '-'}s',
          ),
          const SizedBox(height: 12),
          _LogBlock(title: 'stdout', text: current.stdoutTail),
          if (current.stderrTail.isNotEmpty) ...[
            const SizedBox(height: 8),
            _LogBlock(title: 'stderr', text: current.stderrTail),
          ],
        ],
      ),
    );
  }
}

class _EmptyRunCard extends StatelessWidget {
  const _EmptyRunCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1018),
        borderRadius: BorderRadius.circular(14),
      ),
      child: const Text('Nenhum job recente.'),
    );
  }
}

class _LogBlock extends StatelessWidget {
  const _LogBlock({required this.title, required this.text});

  final String title;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFF08090E),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        text.isEmpty ? '$title: sem saída ainda' : '$title:\n$text',
        style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF2A1114),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(message),
    );
  }
}

class _OpAction {
  const _OpAction({
    required this.label,
    required this.jobKey,
    required this.icon,
    this.params = const {},
  });

  final String label;
  final String jobKey;
  final IconData icon;
  final Map<String, dynamic> params;
}

class _OpGroup {
  const _OpGroup({required this.title, required this.actions});

  final String title;
  final List<_OpAction> actions;
}

String _packageName(String path) {
  if (path.isEmpty) return '-';
  final normalized = path.replaceAll('\\', '/');
  return normalized.split('/').last;
}

String _workflowStage(String stdout) {
  if (stdout.contains('Step 5/5')) return 'Renderizando previews...';
  if (stdout.contains('Step 4/5')) return 'Gerando candidatos...';
  if (stdout.contains('Step 3/5')) return 'Processando vídeos...';
  if (stdout.contains('Step 2/5')) return 'Selecionando melhores...';
  if (stdout.contains('Step 1/5')) return 'Buscando vídeos...';
  return 'Preparando busca...';
}

const _findVideosAction = _OpAction(
  label: 'Encontrar vídeos',
  jobKey: 'find_videos_flow',
  icon: Icons.manage_search_rounded,
  params: {
    'max_videos': 3,
    'max_previews': 10,
    'include_diagnostics': false,
    'download_missing': true,
    'overwrite': true,
  },
);

const _quickActions = [
  _OpAction(
    label: 'Gerar vídeos finais',
    jobKey: 'pipeline_ready_to_post',
    icon: Icons.rocket_launch_rounded,
    params: {
      'download_missing': true,
      'overwrite': true,
      'package_name': 'latest',
    },
  ),
  _OpAction(
    label: 'Package latest',
    jobKey: 'export_ready_to_post_package',
    icon: Icons.inventory_2_rounded,
    params: {'package_name': 'latest'},
  ),
];

const _actionGroups = [
  _OpGroup(
    title: 'Status',
    actions: [
      _OpAction(
        label: 'Atualizar status',
        jobKey: 'batch_status',
        icon: Icons.refresh_rounded,
      ),
    ],
  ),
  _OpGroup(
    title: 'Discovery',
    actions: [
      _OpAction(
        label: 'Descobrir vídeos',
        jobKey: 'discover_podcast_batch',
        icon: Icons.travel_explore_rounded,
      ),
      _OpAction(
        label: 'Ver selecionados',
        jobKey: 'review_selected_videos',
        icon: Icons.fact_check_rounded,
      ),
    ],
  ),
  _OpGroup(
    title: 'Candidates',
    actions: [
      _OpAction(
        label: 'Gerar fila',
        jobKey: 'export_candidate_review_queue',
        icon: Icons.queue_rounded,
        params: {'include_diagnostics': true, 'overwrite': true},
      ),
      _OpAction(
        label: 'Render faltantes',
        jobKey: 'render_candidate_previews',
        icon: Icons.movie_creation_rounded,
        params: {
          'only_missing': true,
          'download_missing': true,
          'overwrite': true,
        },
      ),
      _OpAction(
        label: 'Render 5',
        jobKey: 'render_candidate_previews',
        icon: Icons.filter_5_rounded,
        params: {
          'only_missing': true,
          'download_missing': true,
          'overwrite': true,
          'max_missing': 5,
        },
      ),
      _OpAction(
        label: 'Downloads falhados',
        jobKey: 'list_failed_candidate_downloads',
        icon: Icons.error_outline_rounded,
      ),
    ],
  ),
  _OpGroup(
    title: 'Feedback',
    actions: [
      _OpAction(
        label: 'Exportar feedback',
        jobKey: 'export_feedback_dataset',
        icon: Icons.ios_share_rounded,
      ),
      _OpAction(
        label: 'Analisar feedback',
        jobKey: 'analyze_feedback_dataset',
        icon: Icons.analytics_rounded,
      ),
      _OpAction(
        label: 'Approved plan',
        jobKey: 'export_approved_clips_plan',
        icon: Icons.playlist_add_check_rounded,
      ),
    ],
  ),
  _OpGroup(
    title: 'Produção',
    actions: [
      _OpAction(
        label: 'Pipeline',
        jobKey: 'pipeline_ready_to_post',
        icon: Icons.rocket_launch_rounded,
        params: {
          'download_missing': true,
          'overwrite': true,
          'package_name': 'latest',
        },
      ),
      _OpAction(
        label: 'Package latest',
        jobKey: 'export_ready_to_post_package',
        icon: Icons.inventory_2_rounded,
        params: {'package_name': 'latest'},
      ),
    ],
  ),
  _OpGroup(
    title: 'Manutenção',
    actions: [
      _OpAction(
        label: 'Limpar packages',
        jobKey: 'export_ready_to_post_package',
        icon: Icons.cleaning_services_rounded,
        params: {'clean_old': true},
      ),
    ],
  ),
];
