import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../models/generation_project.dart';
import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import '../widgets/df_button.dart';
import '../widgets/df_card.dart';
import '../widgets/df_error_state.dart';
import '../widgets/df_loading_state.dart';

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
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => const _RegisterPostedSheet(),
    );
    if (saved == true) _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        scrolledUnderElevation: 0,
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
        label: const Text('Registrar'),
      ),
      body: SafeArea(child: _body()),
    );
  }

  Widget _body() {
    if (_error != null) return DfErrorState(message: _error!, onRetry: _load);
    final data = _data;
    if (data == null) {
      return const DfLoadingState(message: 'Carregando desempenho...');
    }
    if (data.totalPosted == 0) return _emptyState();
    return RefreshIndicator(
      onRefresh: () => _load(refresh: true),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
        children: [
          _label('O QUE FUNCIONA'),
          const SizedBox(height: 4),
          const Text('Média de views por estúdio — dobre no que rende.',
              style: AppTextStyles.muted),
          const SizedBox(height: 12),
          for (var i = 0; i < data.byStudio.length; i++) ...[
            if (i > 0) const SizedBox(height: 10),
            _groupCard(i, data.byStudio[i]),
          ],
          const SizedBox(height: 28),
          _label('VÍDEOS POSTADOS'),
          const SizedBox(height: 12),
          for (var i = 0; i < data.videos.length; i++) ...[
            if (i > 0) const SizedBox(height: 10),
            _videoCard(data.videos[i]),
          ],
        ],
      ),
    );
  }

  Widget _emptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                color: AppColors.cyan.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Icon(Icons.insights_rounded, color: AppColors.cyan, size: 30),
            ),
            const SizedBox(height: 18),
            const Text('Sem postagens ainda', style: AppTextStyles.section),
            const SizedBox(height: 8),
            const Text(
              'Poste um vídeo e toque em "Registrar" (cole o link). As views do YouTube entram sozinhas; retenção/CTR você lê no Studio.',
              textAlign: TextAlign.center,
              style: AppTextStyles.muted,
            ),
          ],
        ),
      ),
    );
  }

  Widget _groupCard(int rank, GenerationPerfGroup g) {
    const medals = [AppColors.warning, AppColors.secondaryText, Color(0xFFB87333)];
    final color = rank < medals.length ? medals[rank] : AppColors.muted;
    return DfCard(
      color: AppColors.surfaceAlt,
      child: Row(
        children: [
          Container(
            width: 30,
            height: 30,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.16),
              borderRadius: BorderRadius.circular(9),
            ),
            child: Text('${rank + 1}',
                style: TextStyle(color: color, fontWeight: FontWeight.w900)),
          ),
          const SizedBox(width: 12),
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
                      color: AppColors.cyan,
                      fontWeight: FontWeight.w900,
                      fontSize: 18)),
              const Text('média', style: AppTextStyles.muted),
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
          Text(v.title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.cardTitle),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              _chip(v.personaLabel.isEmpty ? 'Estúdio' : v.personaLabel),
              _chip(v.platform),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 18,
            runSpacing: 8,
            children: [
              _metric(Icons.visibility_rounded, _fmt(v.views), 'views'),
              _metric(Icons.favorite_rounded, _fmt(v.likes), 'likes'),
              if (v.retention > 0)
                _metric(Icons.timelapse_rounded, '${v.retention.toStringAsFixed(0)}%', 'retenção'),
              if (v.ctr > 0)
                _metric(Icons.ads_click_rounded, '${v.ctr.toStringAsFixed(1)}%', 'CTR'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _chip(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border),
      ),
      child: Text(text,
          style: const TextStyle(color: AppColors.secondaryText, fontSize: 11, fontWeight: FontWeight.w700)),
    );
  }

  Widget _metric(IconData icon, String value, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: AppColors.secondaryText),
        const SizedBox(width: 5),
        Text('$value ', style: const TextStyle(color: AppColors.text, fontWeight: FontWeight.w800)),
        Text(label, style: AppTextStyles.muted),
      ],
    );
  }

  Widget _label(String text) {
    return Text(
      text,
      style: const TextStyle(
        color: AppColors.secondaryText,
        fontSize: 11,
        fontWeight: FontWeight.w800,
        letterSpacing: 1.1,
      ),
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
      final rendered = all.where((p) => p.renderStatus == 'ready').toList();
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

  OutlineInputBorder _border(Color c) => OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: c),
      );

  InputDecoration _dec(String label, {String? hint}) => InputDecoration(
        labelText: label,
        hintText: hint,
        labelStyle: const TextStyle(color: AppColors.secondaryText),
        filled: true,
        fillColor: AppColors.surfaceAlt,
        enabledBorder: _border(AppColors.border),
        focusedBorder: _border(AppColors.cyan),
      );

  @override
  Widget build(BuildContext context) {
    final projects = _projects;
    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.only(bottom: 16),
                decoration: BoxDecoration(
                  color: AppColors.border,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ),
            const Text('Registrar postagem', style: AppTextStyles.section),
            const SizedBox(height: 16),
            if (projects == null)
              const Padding(
                padding: EdgeInsets.all(12),
                child: Center(child: CircularProgressIndicator()),
              )
            else
              DropdownButtonFormField<String>(
                initialValue: _projectId,
                isExpanded: true,
                dropdownColor: AppColors.surface,
                decoration: _dec('Vídeo (projeto)'),
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
              dropdownColor: AppColors.surface,
              decoration: _dec('Plataforma'),
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
              decoration: _dec('Link do vídeo', hint: 'https://youtube.com/shorts/...'),
            ),
            const SizedBox(height: 6),
            const Text('YouTube = views automáticas.', style: AppTextStyles.muted),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _retention,
                    keyboardType: TextInputType.number,
                    decoration: _dec('Retenção %'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: _ctr,
                    keyboardType: TextInputType.number,
                    decoration: _dec('CTR %'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _views,
              keyboardType: TextInputType.number,
              decoration: _dec('Views (manual)', hint: 'TikTok / Instagram'),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: AppColors.danger)),
            ],
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              height: 52,
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
