import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import '../widgets/df_action_card.dart';
import '../widgets/df_button.dart';
import '../widgets/df_card.dart';
import '../widgets/df_section_header.dart';
import 'final_clips_screen.dart';
import 'operations_screen.dart';

class MoreScreen extends StatefulWidget {
  const MoreScreen({super.key, required this.onOpenCandidates});

  final VoidCallback onOpenCandidates;

  @override
  State<MoreScreen> createState() => _MoreScreenState();
}

class _MoreScreenState extends State<MoreScreen> {
  final ApiClient _api = ApiClient();
  ApprovedGenerationStatus? _generationStatus;
  bool _loadingGeneration = true;
  bool _triggeringGeneration = false;
  String? _generationError;

  @override
  void initState() {
    super.initState();
    _loadGenerationStatus();
  }

  Future<void> _loadGenerationStatus() async {
    try {
      final status = await _api.fetchApprovedGenerationStatus();
      if (!mounted) return;
      setState(() {
        _generationStatus = status;
        _loadingGeneration = false;
        _generationError = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loadingGeneration = false;
        _generationError = error.toString();
      });
    }
  }

  Future<void> _triggerGeneration({bool retryFailed = false}) async {
    if (_triggeringGeneration) return;
    setState(() => _triggeringGeneration = true);
    try {
      final status = await _api.triggerApprovedGeneration(
        retryFailed: retryFailed,
      );
      if (!mounted) return;
      setState(() {
        _generationStatus = status;
        _triggeringGeneration = false;
        _generationError = null;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Geração de finais iniciada.')),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _generationError = error.toString();
        _triggeringGeneration = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(18),
          children: [
            const Text('Mais', style: AppTextStyles.title),
            const SizedBox(height: 4),
            const Text(
              'Configurações, manutenção e áreas técnicas do DarkFlow.',
              style: TextStyle(color: AppColors.secondaryText),
            ),
            const SizedBox(height: 18),
            const DfSectionHeader(
              title: 'Cortes',
              subtitle: 'Ferramentas avançadas para finais, cache e operações.',
            ),
            _GenerationStatusCard(
              status: _generationStatus,
              loading: _loadingGeneration,
              triggering: _triggeringGeneration,
              error: _generationError,
              onRefresh: _loadGenerationStatus,
              onGeneratePending: () => _triggerGeneration(),
              onRetryFailed: () => _triggerGeneration(retryFailed: true),
            ),
            const SizedBox(height: 12),
            DFActionCard(
              icon: Icons.tune_rounded,
              title: 'Operations / Avançado',
              description:
                  'Acesse jobs técnicos, status do lote, logs e manutenção.',
              buttonLabel: 'Abrir painel técnico',
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => OperationsScreen(
                    onOpenCandidates: () {
                      Navigator.of(context).pop();
                      widget.onOpenCandidates();
                    },
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
            DFActionCard(
              icon: Icons.movie_filter_rounded,
              title: 'Final Clips',
              description:
                  'Revisão final avançada dos vídeos limpos antes do pacote de posts.',
              buttonLabel: 'Abrir finais',
              accent: AppColors.purple,
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const FinalClipsScreen()),
              ),
            ),
            const SizedBox(height: 12),
            const DfSectionHeader(
              title: 'Configurações',
              subtitle: 'Preparando controles para as próximas fases.',
            ),
            const DfCard(
              child: _FutureItem(
                icon: Icons.source_rounded,
                title: 'Fontes',
                subtitle: 'Em breve: canais, consultas e bloqueios.',
              ),
            ),
            const SizedBox(height: 12),
            const DfCard(
              child: _FutureItem(
                icon: Icons.cached_rounded,
                title: 'Cache e armazenamento',
                subtitle: 'Em breve: limpeza fina e limites locais.',
              ),
            ),
            const SizedBox(height: 12),
            const DfCard(
              child: _FutureItem(
                icon: Icons.filter_alt_rounded,
                title: 'Qualidade e filtros',
                subtitle: 'Em breve: presets de score e seleção.',
              ),
            ),
            const SizedBox(height: 12),
            const DfCard(
              child: _FutureItem(
                icon: Icons.history_rounded,
                title: 'Histórico',
                subtitle: 'Em breve: rodadas e pacotes anteriores.',
              ),
            ),
            const SizedBox(height: 12),
            const DfCard(
              child: _FutureItem(
                icon: Icons.info_outline_rounded,
                title: 'Sobre o DarkFlow',
                subtitle: 'MVP local para Cortes agora e Geração em breve.',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _GenerationStatusCard extends StatelessWidget {
  const _GenerationStatusCard({
    required this.status,
    required this.loading,
    required this.triggering,
    required this.error,
    required this.onRefresh,
    required this.onGeneratePending,
    required this.onRetryFailed,
  });

  final ApprovedGenerationStatus? status;
  final bool loading;
  final bool triggering;
  final String? error;
  final VoidCallback onRefresh;
  final VoidCallback onGeneratePending;
  final VoidCallback onRetryFailed;

  @override
  Widget build(BuildContext context) {
    return DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.auto_awesome_motion_rounded,
                color: AppColors.cyan,
              ),
              const SizedBox(width: 10),
              const Expanded(
                child: Text(
                  'Finais automáticos',
                  style: TextStyle(fontWeight: FontWeight.w900),
                ),
              ),
              IconButton(
                onPressed: loading ? null : onRefresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            loading
                ? 'Carregando status...'
                : 'Rodando: ${status?.running == true ? 'sim' : 'não'} · pendentes: ${status?.pendingCount ?? 0} · gerados: ${status?.generatedCount ?? 0} · falhas: ${status?.failedCount ?? 0}',
            style: AppTextStyles.muted,
          ),
          if (error != null) ...[
            const SizedBox(height: 8),
            Text(error!, style: const TextStyle(color: AppColors.danger)),
          ],
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              DFSecondaryButton(
                label: triggering ? 'Iniciando...' : 'Gerar finais pendentes',
                icon: Icons.rocket_launch_rounded,
                onPressed: triggering ? null : onGeneratePending,
              ),
              DFSecondaryButton(
                label: 'Reprocessar falhados',
                icon: Icons.replay_rounded,
                onPressed: triggering ? null : onRetryFailed,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _FutureItem extends StatelessWidget {
  const _FutureItem({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, color: AppColors.cyan),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
              const SizedBox(height: 3),
              Text(subtitle, style: AppTextStyles.muted),
            ],
          ),
        ),
      ],
    );
  }
}
