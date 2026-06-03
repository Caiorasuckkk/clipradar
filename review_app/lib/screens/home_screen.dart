import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../models/ops_status.dart';
import '../models/posts_summary.dart';
import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import '../widgets/df_action_card.dart';
import '../widgets/df_gradient_card.dart';
import '../widgets/df_metric_card.dart';
import '../widgets/df_status_chip.dart';
import 'processing_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.onOpenCandidates,
    required this.onOpenPosts,
  });

  final VoidCallback onOpenCandidates;
  final VoidCallback onOpenPosts;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ApiClient _api = ApiClient();
  OpsStatus? _ops;
  PostsSummary? _posts;
  bool _loading = true;
  bool _starting = false;
  String? _error;

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
      final ops = await _api.fetchOpsStatus();
      final posts = await _api.fetchPostsSummary();
      if (!mounted) return;
      setState(() {
        _ops = ops;
        _posts = posts;
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

  Future<void> _startAnalysis() async {
    if (_starting) return;
    setState(() => _starting = true);
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
      setState(() => _starting = false);
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ProcessingScreen(
            initialRun: run,
            onOpenCandidates: widget.onOpenCandidates,
          ),
        ),
      );
      _load();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _starting = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            padding: const EdgeInsets.all(18),
            children: [
              Row(
                children: [
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Bem-vindo de volta', style: AppTextStyles.muted),
                        SizedBox(height: 4),
                        Text('Olá, Caio', style: AppTextStyles.title),
                        SizedBox(height: 4),
                        Text(
                          'Pronto para analisar novos vídeos?',
                          style: TextStyle(color: AppColors.secondaryText),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    onPressed: _load,
                    icon: _loading
                        ? const SizedBox.square(
                            dimension: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              DFGradientCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const DfStatusChip(label: 'DarkFlow Local'),
                    const SizedBox(height: 16),
                    const Text(
                      'Encontre oportunidades de corte',
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Inicie uma nova rodada de vídeos para avaliar cortes e oportunidades virais.',
                      style: TextStyle(color: AppColors.secondaryText),
                    ),
                    const SizedBox(height: 18),
                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: FilledButton.icon(
                        onPressed: _starting ? null : _startAnalysis,
                        icon: _starting
                            ? const SizedBox.square(
                                dimension: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              )
                            : const Icon(Icons.radar_rounded),
                        label: Text(
                          _starting ? 'Iniciando...' : 'Fazer análise',
                        ),
                      ),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 12),
                      Text(
                        _error!,
                        style: const TextStyle(color: AppColors.danger),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 18),
              LayoutBuilder(
                builder: (context, constraints) {
                  final width = (constraints.maxWidth - 10) / 2;
                  return Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: [
                      SizedBox(
                        width: width,
                        child: DfMetricCard(
                          label: 'Candidatos',
                          value: '${_ops?.totalCandidates ?? 0}',
                        ),
                      ),
                      SizedBox(
                        width: width,
                        child: DfMetricCard(
                          label: 'Previews prontos',
                          value: '${_ops?.previewReady ?? 0}',
                        ),
                      ),
                      SizedBox(
                        width: width,
                        child: DfMetricCard(
                          label: 'Ready to post',
                          value: '${_ops?.readyToPost ?? 0}',
                        ),
                      ),
                      SizedBox(
                        width: width,
                        child: DfMetricCard(
                          label: 'Postados',
                          value: '${_posts?.posted ?? 0}',
                        ),
                      ),
                    ],
                  );
                },
              ),
              const SizedBox(height: 18),
              DFActionCard(
                icon: Icons.swipe_rounded,
                title: 'Avaliar candidatos',
                description:
                    'Continue a revisão dos previews prontos no formato mobile.',
                buttonLabel: 'Abrir avaliação',
                onPressed: widget.onOpenCandidates,
              ),
              const SizedBox(height: 12),
              DFActionCard(
                icon: Icons.publish_rounded,
                title: 'Postagem manual',
                description:
                    'Copie títulos, descrições e hashtags dos vídeos prontos.',
                buttonLabel: 'Abrir posts',
                onPressed: widget.onOpenPosts,
                accent: AppColors.purple,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
