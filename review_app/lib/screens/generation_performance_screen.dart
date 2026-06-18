import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../models/generation_project.dart';
import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import '../widgets/df_button.dart';
import '../widgets/df_card.dart';
import '../widgets/df_error_state.dart';
import '../widgets/df_loading_state.dart';
import '../widgets/df_section_header.dart';

/// Performance loop: log posted videos and see what works (by studio) so we can
/// double down. YouTube views are pulled automatically; retention/CTR are manual.
class GenerationPerformanceScreen extends StatefulWidget {
  const GenerationPerformanceScreen({super.key});

  @override
  State<GenerationPerformanceScreen> createState() =>
      _GenerationPerformanceScreenState();
}

class _GenerationPerformanceScreenState extends State<GenerationPerformanceScreen> {
  final ApiClient _api = ApiClient();
  GenerationPerformance? _data;
  String? _error;
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load({bool refresh = false}) async {
    setState(() {
      _error = null;
      if (refresh) _refreshing = true;
    });
    try {
      final data = await _api.fetchGenerationPerformance(refresh: refresh);
      if (!mounted) return;
      setState(() {
        _data = data;
        _refreshing = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _refreshing = false;
      });
    }
  }

  Future<void> _openRegister() async {
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      builder: (_) => const _RegisterPostedSheet(),
    );
    if (saved == true) _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Desempenho'),
        actions: [
          IconButton(
            tooltip: 'Atualizar views (YouTube)',
            onPressed: _refreshing ? null : () => _load(refresh: true),
            icon: _refreshing
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openRegister,
        icon: const Icon(Icons.add_rounded),
        label: const Text('Registrar postagem'),
      ),
      body: SafeArea(child: _body()),
    );
  }

  Widget _body() {
    if (_error != null) return DfErrorState(message: _error!, onRetry: _load);
    final data = _data;
    if (data == null) return const DfLoadingState(message: 'Carregando desempenho...');
    if (data.totalPosted == 0) {
      return ListView(
        padding: const EdgeInsets.all(18),
        children: const [
          DfSectionHeader(
            title: 'Sem postagens ainda',
            subtitle:
                'Poste um vídeo e toque em "Registrar postagem" (cole o link). As views do YouTube entram sozinhas; retenção/CTR você lê no Studio.',
          ),
        ],
      );
    }
    return RefreshIndicator(
      onRefresh: () => _load(refresh: true),
      child: ListView(
        padding: const EdgeInsets.all(18),
        children: [
          const DfSectionHeader(
            title: 'O que funciona',
            subtitle: 'Média de views por estúdio — dobre no que rende.',
          ),
          ...data.byStudio.map(_groupCard),
          const SizedBox(height: 18),
          const DfSectionHeader(title: 'Vídeos postados'),
          ...data.videos.map(_videoCard),
        ],
      ),
    );
  }

  Widget _groupCard(GenerationPerfGroup g) {
    return DfCard(
      color: AppColors.surfaceAlt,
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(g.name, style: AppTextStyles.cardTitle),
                Text('${g.count} vídeo(s)', style: AppTextStyles.muted),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(_fmt(g.avgViews.round()),
                  style: const TextStyle(
                      color: AppColors.cyan, fontWeight: FontWeight.w900, fontSize: 18)),
              const Text('média de views', style: AppTextStyles.muted),
            ],
          ),
        ],
      ),
    );
  }

  Widget _videoCard(GenerationPerfVideo v) {
    return DfCard(
      color: AppColors.surfaceAlt,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(v.title, maxLines: 2, overflow: TextOverflow.ellipsis, style: AppTextStyles.cardTitle),
          const SizedBox(height: 4),
          Text('${v.personaLabel} · ${v.platform}', style: AppTextStyles.muted),
          const SizedBox(height: 8),
          Wrap(
            spacing: 16,
            children: [
              _metric(Icons.visibility_rounded, _fmt(v.views), 'views'),
              _metric(Icons.favorite_rounded, _fmt(v.likes), 'likes'),
              if (v.retention > 0) _metric(Icons.timelapse_rounded, '${v.retention.toStringAsFixed(0)}%', 'retenção'),
              if (v.ctr > 0) _metric(Icons.ads_click_rounded, '${v.ctr.toStringAsFixed(1)}%', 'CTR'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _metric(IconData icon, String value, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: AppColors.secondaryText),
        const SizedBox(width: 4),
        Text('$value ', style: const TextStyle(fontWeight: FontWeight.w700)),
        Text(label, style: AppTextStyles.muted),
      ],
    );
  }

  static String _fmt(int n) {
    if (n >= 1000000) return '${(n / 1000000).toStringAsFixed(1)}M';
    if (n >= 1000) return '${(n / 1000).toStringAsFixed(1)}k';
    return '$n';
  }
}

class _RegisterPostedSheet extends StatefulWidget {
  const _RegisterPostedSheet();

  @override
  State<_RegisterPostedSheet> createState() => _RegisterPostedSheetState();
}

class _RegisterPostedSheetState extends State<_RegisterPostedSheet> {
  final ApiClient _api = ApiClient();
  final _url = TextEditingController();
  final _retention = TextEditingController();
  final _ctr = TextEditingController();
  final _views = TextEditingController();

  List<GenerationProject>? _projects;
  String? _projectId;
  String _platform = 'youtube';
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadProjects();
  }

  Future<void> _loadProjects() async {
    try {
      final all = await _api.getGenerationProjects();
      final rendered =
          all.where((p) => p.renderStatus == 'ready').toList();
      if (!mounted) return;
      setState(() => _projects = rendered.isNotEmpty ? rendered : all);
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    }
  }

  @override
  void dispose() {
    _url.dispose();
    _retention.dispose();
    _ctr.dispose();
    _views.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_projectId == null) {
      setState(() => _error = 'Escolha o vídeo (projeto).');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await _api.markGenerationProjectPosted(
        projectId: _projectId!,
        platform: _platform,
        url: _url.text.trim(),
        views: int.tryParse(_views.text.trim()),
        retention: double.tryParse(_retention.text.trim().replaceAll(',', '.')),
        ctr: double.tryParse(_ctr.text.trim().replaceAll(',', '.')),
      );
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _saving = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final projects = _projects;
    return Padding(
      padding: EdgeInsets.only(
        left: 18,
        right: 18,
        top: 18,
        bottom: MediaQuery.of(context).viewInsets.bottom + 18,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Registrar postagem', style: AppTextStyles.title),
            const SizedBox(height: 12),
            if (projects == null)
              const Padding(
                padding: EdgeInsets.all(12),
                child: Center(child: CircularProgressIndicator()),
              )
            else
              DropdownButtonFormField<String>(
                initialValue: _projectId,
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Vídeo (projeto)',
                  border: OutlineInputBorder(),
                ),
                items: projects
                    .map((p) => DropdownMenuItem(
                          value: p.projectId,
                          child: Text(p.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                        ))
                    .toList(),
                onChanged: (v) => setState(() => _projectId = v),
              ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _platform,
              decoration: const InputDecoration(
                labelText: 'Plataforma',
                border: OutlineInputBorder(),
              ),
              items: const [
                DropdownMenuItem(value: 'youtube', child: Text('YouTube')),
                DropdownMenuItem(value: 'tiktok', child: Text('TikTok')),
                DropdownMenuItem(value: 'instagram', child: Text('Instagram')),
              ],
              onChanged: (v) => setState(() => _platform = v ?? 'youtube'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _url,
              decoration: const InputDecoration(
                labelText: 'Link do vídeo (YouTube = views automáticas)',
                hintText: 'https://youtube.com/shorts/...',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _retention,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'Retenção %',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: _ctr,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'CTR %',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _views,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Views (manual, p/ TikTok/Instagram)',
                border: OutlineInputBorder(),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 10),
              Text(_error!, style: const TextStyle(color: AppColors.danger)),
            ],
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: DFPrimaryButton(
                label: _saving ? 'Salvando...' : 'Salvar',
                icon: Icons.save_rounded,
                onPressed: _saving ? null : _save,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
