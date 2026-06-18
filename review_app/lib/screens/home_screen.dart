import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/search_presets.dart';
import '../models/ops_status.dart';
import '../models/posts_summary.dart';
import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import '../widgets/df_button.dart';
import '../widgets/df_card.dart';
import '../widgets/df_gradient_card.dart';
import '../widgets/df_metric_card.dart';
import '../widgets/df_section_header.dart';
import '../widgets/df_status_chip.dart';
import 'generation_auto_screen.dart';
import 'generation_performance_screen.dart';
import 'processing_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.onOpenCandidates,
    required this.onOpenPosts,
    required this.onOpenAnalytics,
    required this.onOpenGeneration,
  });

  final VoidCallback onOpenCandidates;
  final VoidCallback onOpenPosts;
  final VoidCallback onOpenAnalytics;
  final VoidCallback onOpenGeneration;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ApiClient _api = ApiClient();
  OpsStatus? _ops;
  PostsSummary? _posts;
  bool _loading = true;
  String? _startingMode;
  String? _error;

  bool get _starting => _startingMode != null;

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

  Future<void> _startAnalysis({required bool deep}) async {
    if (_starting) return;
    setState(() => _startingMode = deep ? 'deep' : 'quick');
    try {
      final result = await _api.startOpsJobWithResult(
        jobKey: 'find_videos_flow',
        params: deep ? deepSearchParams : quickSearchParams,
      );
      if (!mounted) return;
      setState(() => _startingMode = null);
      if (result.alreadyRunning) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              result.message.isEmpty
                  ? 'Uma busca já está em andamento.'
                  : result.message,
            ),
          ),
        );
      }
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ProcessingScreen(
            initialRun: result.run,
            onOpenCandidates: widget.onOpenCandidates,
            onOpenHome: () {},
            onOpenPosts: widget.onOpenPosts,
            onOpenReviewed: widget.onOpenCandidates,
          ),
        ),
      );
      _load();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _startingMode = null;
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
                        Text('DarkFlow', style: AppTextStyles.title),
                        SizedBox(height: 4),
                        Text(
                          'Cortes e geração de shorts em um fluxo local.',
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
                      'Escolha como criar seu próximo short',
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Transforme vídeos longos em cortes prontos ou prepare a criação do zero na nova área de Geração.',
                      style: TextStyle(color: AppColors.secondaryText),
                    ),
                    const SizedBox(height: 18),
                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: FilledButton.icon(
                        onPressed: _starting
                            ? null
                            : () => _startAnalysis(deep: false),
                        icon: _starting
                            ? const SizedBox.square(
                                dimension: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              )
                            : const Icon(Icons.radar_rounded),
                        label: Text(
                          _startingMode == 'quick'
                              ? 'Iniciando...'
                              : 'Busca rápida',
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: OutlinedButton.icon(
                        onPressed: _starting
                            ? null
                            : () => _startAnalysis(deep: true),
                        icon: _startingMode == 'deep'
                            ? const SizedBox.square(
                                dimension: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              )
                            : const Icon(Icons.travel_explore_rounded),
                        label: Text(
                          _startingMode == 'deep'
                              ? 'Iniciando...'
                              : 'Busca profunda',
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
              const DfSectionHeader(
                title: 'Áreas principais',
                subtitle: 'Comece pelos cortes ou explore a geração do zero.',
              ),
              _WorkspaceCard(
                icon: Icons.movie_filter_rounded,
                title: 'Cortes',
                description:
                    'Transforme vídeos longos em cortes prontos para revisar.',
                accent: AppColors.cyan,
                actions: [
                  DFPrimaryButton(
                    label: 'Buscar cortes',
                    icon: Icons.radar_rounded,
                    onPressed: _starting
                        ? null
                        : () => _startAnalysis(deep: false),
                  ),
                  DFSecondaryButton(
                    label: 'Avaliar pendentes',
                    icon: Icons.swipe_rounded,
                    onPressed: widget.onOpenCandidates,
                  ),
                  DFSecondaryButton(
                    label: 'Ver analytics',
                    icon: Icons.query_stats_rounded,
                    onPressed: widget.onOpenAnalytics,
                  ),
                ],
              ),
              const SizedBox(height: 12),
              _WorkspaceCard(
                icon: Icons.auto_awesome_rounded,
                title: 'Geração',
                description:
                    'Crie shorts narrados do zero com roteiro, voz e visual.',
                accent: AppColors.purple,
                actions: [
                  DFPrimaryButton(
                    label: 'Gerar vídeo automático',
                    icon: Icons.auto_awesome_rounded,
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const GenerationAutoScreen(),
                      ),
                    ),
                  ),
                  DFSecondaryButton(
                    label: 'Modo avançado',
                    icon: Icons.edit_note_rounded,
                    onPressed: widget.onOpenGeneration,
                  ),
                  DFSecondaryButton(
                    label: 'Ver projetos',
                    icon: Icons.folder_copy_rounded,
                    onPressed: widget.onOpenGeneration,
                  ),
                  DFSecondaryButton(
                    label: 'Desempenho',
                    icon: Icons.query_stats_rounded,
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const GenerationPerformanceScreen(),
                      ),
                    ),
                  ),
                ],
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
                          label: 'Cortes',
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
            ],
          ),
        ),
      ),
    );
  }
}

class _WorkspaceCard extends StatelessWidget {
  const _WorkspaceCard({
    required this.icon,
    required this.title,
    required this.description,
    required this.actions,
    required this.accent,
  });

  final IconData icon;
  final String title;
  final String description;
  final List<Widget> actions;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return DfCard(
      color: AppColors.surfaceAlt,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Icon(icon, color: accent),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: AppTextStyles.cardTitle),
                    const SizedBox(height: 4),
                    Text(
                      description,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.muted,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          LayoutBuilder(
            builder: (context, constraints) {
              final isWide = constraints.maxWidth > 430;
              if (isWide) {
                return Row(
                  children: [
                    for (var index = 0; index < actions.length; index++) ...[
                      Expanded(child: actions[index]),
                      if (index < actions.length - 1) const SizedBox(width: 8),
                    ],
                  ],
                );
              }
              return Column(
                children: [
                  for (var index = 0; index < actions.length; index++) ...[
                    SizedBox(width: double.infinity, child: actions[index]),
                    if (index < actions.length - 1) const SizedBox(height: 8),
                  ],
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}
