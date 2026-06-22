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
import '../widgets/df_status_chip.dart';
import 'generation_auto_screen.dart';
import 'generation_performance_screen.dart';
import 'generation_projects_screen.dart';
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

  void _openGenerate() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const GenerationAutoScreen()),
    );
  }

  void _openPerformance() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const GenerationPerformanceScreen()),
    );
  }

  void _openProjects() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const GenerationProjectsScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
            children: [
              _header(),
              const SizedBox(height: 22),
              _hero(),
              const SizedBox(height: 28),
              _label('ÁREAS'),
              const SizedBox(height: 12),
              _generationCard(),
              const SizedBox(height: 12),
              _cortesCard(),
              if (_error != null) ...[
                const SizedBox(height: 14),
                _errorBanner(_error!),
              ],
              const SizedBox(height: 28),
              _label('NÚMEROS'),
              const SizedBox(height: 12),
              _metrics(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _header() {
    return Row(
      children: [
        const Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Bem-vindo de volta', style: AppTextStyles.muted),
              SizedBox(height: 4),
              Text('DarkFlow', style: AppTextStyles.title),
            ],
          ),
        ),
        IconButton(
          onPressed: _load,
          icon: _loading
              ? const SizedBox.square(
                  dimension: 18, child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.refresh_rounded),
        ),
      ],
    );
  }

  Widget _hero() {
    return DFGradientCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const DfStatusChip(label: 'DarkFlow Local'),
          const SizedBox(height: 16),
          const Text('Crie seu próximo short', style: AppTextStyles.title),
          const SizedBox(height: 8),
          Text(
            'Tema → roteiro, voz e visual, automático. Em português e inglês.',
            style: AppTextStyles.body.copyWith(color: AppColors.secondaryText),
          ),
          const SizedBox(height: 18),
          SizedBox(
            width: double.infinity,
            child: DFPrimaryButton(
              label: 'Gerar vídeo automático',
              icon: Icons.auto_awesome_rounded,
              onPressed: _openGenerate,
            ),
          ),
        ],
      ),
    );
  }

  Widget _generationCard() {
    return _WorkspaceCard(
      icon: Icons.auto_awesome_rounded,
      title: 'Geração',
      description: 'Shorts narrados do zero com a persona Marco.',
      accent: AppColors.purple,
      actions: [
        DFPrimaryButton(
          label: 'Criar vídeo',
          icon: Icons.auto_awesome_rounded,
          onPressed: _openGenerate,
        ),
        DFSecondaryButton(
          label: 'Desempenho',
          icon: Icons.query_stats_rounded,
          onPressed: _openPerformance,
        ),
        DFSecondaryButton(
          label: 'Projetos',
          icon: Icons.folder_copy_rounded,
          onPressed: _openProjects,
        ),
      ],
    );
  }

  Widget _cortesCard() {
    return _WorkspaceCard(
      icon: Icons.movie_filter_rounded,
      title: 'Cortes',
      description: 'Transforme vídeos longos em cortes prontos.',
      accent: AppColors.cyan,
      actions: [
        DFPrimaryButton(
          label: _startingMode == 'quick' ? 'Iniciando...' : 'Buscar cortes',
          icon: Icons.radar_rounded,
          onPressed: _starting ? null : () => _startAnalysis(deep: false),
        ),
        DFSecondaryButton(
          label: 'Avaliar pendentes',
          icon: Icons.swipe_rounded,
          onPressed: widget.onOpenCandidates,
        ),
        DFSecondaryButton(
          label: 'Analytics',
          icon: Icons.query_stats_rounded,
          onPressed: widget.onOpenAnalytics,
        ),
      ],
    );
  }

  Widget _metrics() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = (constraints.maxWidth - 10) / 2;
        return Wrap(
          spacing: 10,
          runSpacing: 10,
          children: [
            SizedBox(width: width, child: DfMetricCard(label: 'Cortes', value: '${_ops?.totalCandidates ?? 0}')),
            SizedBox(width: width, child: DfMetricCard(label: 'Previews prontos', value: '${_ops?.previewReady ?? 0}')),
            SizedBox(width: width, child: DfMetricCard(label: 'Ready to post', value: '${_ops?.readyToPost ?? 0}')),
            SizedBox(width: width, child: DfMetricCard(label: 'Postados', value: '${_posts?.posted ?? 0}')),
          ],
        );
      },
    );
  }

  Widget _label(String text) {
    return Text(text, style: AppTextStyles.label);
  }

  Widget _errorBanner(String message) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.danger.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.danger.withValues(alpha: 0.4)),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline_rounded, color: AppColors.danger, size: 18),
          const SizedBox(width: 8),
          Expanded(child: Text(message, style: const TextStyle(color: AppColors.danger))),
        ],
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
      padding: const EdgeInsets.all(16),
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
                  borderRadius: BorderRadius.circular(14),
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
                    Text(description,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.muted),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
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
