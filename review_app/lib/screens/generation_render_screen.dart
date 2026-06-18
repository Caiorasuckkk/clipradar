import 'dart:async';

import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

import '../core/api_client.dart';
import '../models/generation_project.dart';
import '../models/generation_render.dart';
import '../theme/app_colors.dart';
import '../theme/app_text_styles.dart';
import '../widgets/df_button.dart';
import '../widgets/df_card.dart';
import '../widgets/df_page_scaffold.dart';
import '../widgets/df_status_chip.dart';

/// Render readiness + progress + preview for a single generation project.
///
/// Shows a readiness checklist, prepares prerequisites (words.json fallback,
/// marking visuals ready), enqueues the background render, polls `/render/status`
/// and plays the resulting MP4 inline once ready.
class GenerationRenderScreen extends StatefulWidget {
  const GenerationRenderScreen({
    super.key,
    required this.api,
    required this.project,
  });

  final ApiClient api;
  final GenerationProject project;

  @override
  State<GenerationRenderScreen> createState() => _GenerationRenderScreenState();
}

class _GenerationRenderScreenState extends State<GenerationRenderScreen> {
  late GenerationProject _project;
  GenerationRenderStatus? _status;
  VideoPlayerController? _videoController;
  bool _loading = true;
  bool _busy = false;
  bool _polling = false;
  bool _offerFallback = false;
  String _error = '';
  String _info = '';

  String get _projectId => _project.projectId;

  @override
  void initState() {
    super.initState();
    _project = widget.project;
    _loadInitial();
  }

  @override
  void dispose() {
    _polling = false;
    _videoController?.dispose();
    super.dispose();
  }

  // -- Readiness checklist -------------------------------------------------

  List<GenerationVisualItem> get _usableItems => _project.visualItems
      .where((item) => item.status != 'rejected')
      .toList();
  int get _mediaCount => _usableItems
      .where((item) => item.mediaPath.isNotEmpty || item.mediaUrl.isNotEmpty)
      .length;

  bool get _voiceReady => _project.voiceStatus == 'ready';
  bool get _wordsReady => _project.voiceWordCount > 0;
  bool get _hasVisualItems => _usableItems.isNotEmpty;
  bool get _mediaReady => _mediaCount > 0;
  bool get _visualReady => _project.visualStatus == 'ready';
  bool get _statusReady => _project.status == 'ready_for_render' ||
      _project.status == 'rendered';
  bool get _isReadyForRender =>
      _voiceReady && _wordsReady && _hasVisualItems && _visualReady;

  // -- Data ----------------------------------------------------------------

  Future<void> _loadInitial() async {
    try {
      final status = await widget.api.fetchGenerationRenderStatus(_projectId);
      if (!mounted) return;
      setState(() {
        _status = status;
        _loading = false;
      });
      if (status.isReady) {
        await _prepareVideo();
      } else if (status.isWorking) {
        _startPolling();
      }
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = _friendlyError(error);
      });
    }
  }

  Future<void> _refreshProject() async {
    try {
      final project = await widget.api.fetchGenerationProject(_projectId);
      if (mounted) setState(() => _project = project);
    } catch (_) {
      // Non-fatal: checklist keeps the last known project.
    }
  }

  Future<void> _refreshStatus() async {
    try {
      final status = await widget.api.fetchGenerationRenderStatus(_projectId);
      if (mounted) setState(() => _status = status);
    } catch (_) {
      // Non-fatal.
    }
  }

  // -- Prepare -------------------------------------------------------------

  Future<GenerationRenderPrepare?> _prepare({required bool allowFallback}) async {
    final result = await widget.api.prepareGenerationRender(
      _projectId,
      markVisualReady: true,
      allowVisualFallback: allowFallback,
    );
    if (result.project != null && mounted) {
      setState(() => _project = result.project!);
    }
    return result;
  }

  /// "Preparar qualidade": ensure words/captions and download real b-roll from
  /// Pexels (no fallback) so the render uses real visuals when possible.
  Future<void> _onPrepareQuality() async {
    setState(() {
      _busy = true;
      _error = '';
      _info = '';
    });
    try {
      final result = await _prepare(allowFallback: false);
      if (!mounted || result == null) return;
      await _refreshStatus();
      if (result.mediaCount > 0) {
        setState(() => _info =
            '${result.pexelsDownloadedCount} mídia(s) baixada(s) do Pexels.');
      } else {
        setState(() {
          _offerFallback = true;
          _error = result.pexelsAvailable
              ? 'O Pexels não retornou mídia para estas queries. Você pode renderizar com fallback visual.'
              : 'Pexels não configurado (PEXELS_API_KEY). Você pode renderizar com fallback visual.';
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = _friendlyError(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  // -- Render --------------------------------------------------------------

  Future<void> _onRender({required bool allowFallback}) async {
    setState(() {
      _busy = true;
      _error = '';
      _info = '';
    });
    try {
      if (!_isReadyForRender || allowFallback) {
        final result = await _prepare(allowFallback: allowFallback);
        if (result != null && !result.readyForRender) {
          if (mounted) {
            setState(() {
              _busy = false;
              _offerFallback = result.mediaCount == 0;
              _error = _missingMessage(result.missing);
            });
          }
          return;
        }
      }
      await widget.api.startGenerationRender(
        _projectId,
        allowVisualFallback: allowFallback,
        force: true,
      );
      if (!mounted) return;
      setState(() => _busy = false);
      await _disposeVideo();
      await _refreshProject();
      _startPolling();
    } catch (error) {
      if (mounted) {
        setState(() {
          _busy = false;
          if (error.toString().contains('missing_visual_media')) {
            _offerFallback = true;
          }
          _error = _friendlyError(error);
        });
      }
    }
  }

  Future<void> _cancelRender() async {
    final jobId = _status?.job?.id ?? '';
    if (jobId.isEmpty) return;
    setState(() => _busy = true);
    try {
      await widget.api.cancelGenerationJob(jobId);
      await _refreshOnce();
    } catch (error) {
      if (mounted) setState(() => _error = _friendlyError(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  // -- Polling -------------------------------------------------------------

  void _startPolling() {
    if (_polling) return;
    _polling = true;
    _pollLoop();
  }

  Future<void> _pollLoop() async {
    while (_polling && mounted) {
      await Future<void>.delayed(const Duration(seconds: 2));
      if (!_polling || !mounted) break;
      final keepGoing = await _refreshOnce();
      if (!keepGoing) break;
    }
    _polling = false;
  }

  Future<bool> _refreshOnce() async {
    try {
      final status = await widget.api.fetchGenerationRenderStatus(_projectId);
      if (!mounted) return false;
      setState(() => _status = status);
      if (status.isReady) {
        await _refreshProject();
        await _prepareVideo();
        return false;
      }
      final job = status.job;
      if (job != null && job.isTerminal && !status.isWorking) {
        await _refreshProject();
        return false;
      }
      return status.isWorking;
    } catch (error) {
      if (mounted) setState(() => _error = _friendlyError(error));
      return true; // transient: keep polling
    }
  }

  // -- Video ---------------------------------------------------------------

  Future<void> _prepareVideo() async {
    await _disposeVideo();
    final controller = VideoPlayerController.networkUrl(
      Uri.parse(widget.api.generationRenderVideoUrl(_projectId)),
    );
    try {
      await controller.initialize();
      await controller.setLooping(true);
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() => _videoController = controller);
    } catch (error) {
      await controller.dispose();
      if (mounted) setState(() => _error = 'Falha ao carregar o vídeo: $error');
    }
  }

  Future<void> _disposeVideo() async {
    final controller = _videoController;
    _videoController = null;
    if (controller != null) await controller.dispose();
  }

  // -- Build ---------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final status = _status;
    final working = status?.isWorking ?? false;
    return DfPageScaffold(
      title: 'Render',
      subtitle: _project.title,
      trailing: IconButton(
        onPressed: () => Navigator.of(context).maybePop(),
        icon: const Icon(Icons.close_rounded),
      ),
      children: [
        if (_loading)
          const DfCard(
            child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
          )
        else ...[
          if (_error.isNotEmpty) _ErrorCard(text: _error),
          if (_info.isNotEmpty) _InfoCard(text: _info),
          if (status != null && status.isStale)
            const _WarningCard(
              text:
                  'O vídeo precisa ser renderizado novamente após mudanças de voz/visual.',
            ),
          if (status != null) _statusCard(status),
          const SizedBox(height: 14),
          if (status?.isReady == true && _videoController != null)
            _videoCard(_videoController!),
          if (working) _workingCard(status!),
          if (!working && status?.isReady != true) _checklistCard(),
          const SizedBox(height: 4),
          _actions(working: working, isReady: status?.isReady ?? false),
        ],
      ],
    );
  }

  Widget _statusCard(GenerationRenderStatus status) {
    return DfCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('Status do vídeo', style: AppTextStyles.cardTitle),
              const Spacer(),
              DfStatusChip(
                label: status.renderStatus,
                status: status.isReady
                    ? 'success'
                    : (status.renderStatus == 'failed' ? 'danger' : 'warning'),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              if ((status.durationSeconds ?? 0) > 0)
                DfStatusChip(label: '${status.durationSeconds!.round()}s'),
              if ((status.segmentCount ?? 0) > 0)
                DfStatusChip(label: '${status.segmentCount} cenas'),
              const DfStatusChip(label: '1080x1920'),
              if (status.narrationStyleLabel.isNotEmpty)
                DfStatusChip(label: '🎙 ${status.narrationStyleLabel}'),
              if (status.visualItemCount > 0)
                DfStatusChip(
                  label:
                      '${status.visualMediaCount}/${status.visualItemCount} mídias Pexels',
                  status: status.visualMediaCount >= status.visualItemCount
                      ? 'success'
                      : '',
                ),
              if (status.visualFallbackUsed)
                const DfStatusChip(
                  label: 'fallback visual',
                  status: 'warning',
                ),
            ],
          ),
          if (status.visualFallbackUsed) ...[
            const SizedBox(height: 8),
            Text(
              'Sem b-roll real: cenas usam fundo visual gerado. Adicione Pexels para b-roll.',
              style: AppTextStyles.muted,
            ),
          ],
          if (status.error.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(status.error, style: const TextStyle(color: AppColors.warning)),
          ],
        ],
      ),
    );
  }

  Widget _checklistCard() {
    final status = _status;
    final captionsReady = (status?.captionCount ?? 0) > 0;
    final timestampsReady = (status?.wordCount ?? 0) > 0 || _wordsReady;
    final mediaCount = status?.visualMediaCount ?? _mediaCount;
    final itemCount = status?.visualItemCount ?? _usableItems.length;
    final qualityVisual = itemCount > 0 && mediaCount >= itemCount;
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: DfCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Qualidade do render', style: AppTextStyles.cardTitle),
            const SizedBox(height: 12),
            _checkRow('Voz pronta', _voiceReady),
            _checkRow('Timestamps sincronizados', timestampsReady),
            _checkRow('Captions geradas', captionsReady),
            _checkRow('Assets visuais baixados', mediaCount > 0),
            _checkRow('Qualidade visual (b-roll real)', qualityVisual),
            _checkRow('Pronto para render', _statusReady),
            if (itemCount > 0)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(
                  '$mediaCount de $itemCount itens com mídia real do Pexels.',
                  style: AppTextStyles.muted,
                ),
              ),
            if (mediaCount < itemCount) ...[
              const SizedBox(height: 2),
              Text(
                '${itemCount - mediaCount} item(ns) sem b-roll real (usarão fallback).',
                style: const TextStyle(color: AppColors.warning),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _checkRow(String label, bool ok) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(
            ok ? Icons.check_circle_rounded : Icons.radio_button_unchecked,
            size: 20,
            color: ok ? AppColors.success : AppColors.muted,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              style: TextStyle(
                color: ok ? AppColors.text : AppColors.secondaryText,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _workingCard(GenerationRenderStatus status) {
    final job = status.job;
    final step = (job?.step.isNotEmpty ?? false) ? job!.step : 'preparando';
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: DfCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Renderizando • $step', style: AppTextStyles.cardTitle),
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: status.progress > 0 ? status.progress : null,
                minHeight: 8,
                backgroundColor: AppColors.border,
              ),
            ),
            const SizedBox(height: 8),
            Text('${(status.progress * 100).round()}%',
                style: AppTextStyles.muted),
          ],
        ),
      ),
    );
  }

  Widget _videoCard(VideoPlayerController controller) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: DfCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Pré-visualização', style: AppTextStyles.cardTitle),
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: AspectRatio(
                aspectRatio: controller.value.aspectRatio == 0
                    ? 9 / 16
                    : controller.value.aspectRatio,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    VideoPlayer(controller),
                    _PlayPauseOverlay(controller: controller),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            Text(
              'Revise antes de publicar. Lembre o disclosure de IA nas plataformas.',
              style: AppTextStyles.muted,
            ),
          ],
        ),
      ),
    );
  }

  Widget _actions({required bool working, required bool isReady}) {
    final children = <Widget>[];
    if (working) {
      children.add(
        DFSecondaryButton(
          label: 'Cancelar',
          icon: Icons.stop_circle_outlined,
          onPressed: _busy ? null : _cancelRender,
        ),
      );
    } else {
      children.add(
        DFSecondaryButton(
          label: 'Preparar qualidade',
          icon: Icons.auto_fix_high_rounded,
          onPressed: _busy ? null : _onPrepareQuality,
        ),
      );
      children.add(
        DFPrimaryButton(
          label: (isReady || (_status?.isStale ?? false))
              ? 'Renderizar novamente'
              : 'Renderizar',
          icon: Icons.movie_creation_rounded,
          onPressed: _busy ? null : () => _onRender(allowFallback: false),
        ),
      );
      // Visible-fallback render is offered only when there is no real media,
      // so the user never assumes b-roll that doesn't exist.
      if (_offerFallback || (_hasVisualItems && !_mediaReady)) {
        children.add(
          DFSecondaryButton(
            label: 'Renderizar com fallback visual',
            icon: Icons.gradient_rounded,
            onPressed: _busy ? null : () => _onRender(allowFallback: true),
          ),
        );
      }
    }
    return Wrap(spacing: 8, runSpacing: 8, children: children);
  }

  // -- Helpers -------------------------------------------------------------

  String _missingMessage(List<String> missing) {
    if (missing.isEmpty) return '';
    final labels = missing.map(_missingLabel).toList();
    return 'Faltando para renderizar: ${labels.join(', ')}.';
  }

  String _missingLabel(String code) {
    switch (code) {
      case 'missing_voice_audio':
        return 'narração (voz)';
      case 'missing_voice_words':
        return 'timestamps da voz';
      case 'missing_visual_items':
        return 'itens visuais';
      case 'missing_visual_media':
        return 'mídia visual (baixar Pexels ou usar fallback)';
      case 'visual_not_ready':
        return 'marcar visual pronto';
      case 'project_not_ready_for_render':
        return 'projeto pronto para render';
      default:
        return code;
    }
  }

  String _friendlyError(Object error) {
    final text = error.toString();
    if (text.contains('missing_voice_audio')) {
      return 'Gere a narração (voz) antes de renderizar.';
    }
    if (text.contains('missing_visual_items')) {
      return 'Adicione itens visuais antes de renderizar.';
    }
    return text.replaceFirst('Exception: ', '');
  }
}

class _PlayPauseOverlay extends StatefulWidget {
  const _PlayPauseOverlay({required this.controller});

  final VideoPlayerController controller;

  @override
  State<_PlayPauseOverlay> createState() => _PlayPauseOverlayState();
}

class _PlayPauseOverlayState extends State<_PlayPauseOverlay> {
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        setState(() {
          widget.controller.value.isPlaying
              ? widget.controller.pause()
              : widget.controller.play();
        });
      },
      child: AnimatedOpacity(
        opacity: widget.controller.value.isPlaying ? 0.0 : 1.0,
        duration: const Duration(milliseconds: 200),
        child: Container(
          color: Colors.black26,
          child: const Center(
            child: Icon(
              Icons.play_circle_fill_rounded,
              size: 72,
              color: Colors.white,
            ),
          ),
        ),
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: DfCard(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.error_outline_rounded, color: AppColors.danger),
            const SizedBox(width: 12),
            Expanded(
              child:
                  Text(text, style: const TextStyle(color: AppColors.danger)),
            ),
          ],
        ),
      ),
    );
  }
}

class _WarningCard extends StatelessWidget {
  const _WarningCard({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: DfCard(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.refresh_rounded, color: AppColors.warning),
            const SizedBox(width: 12),
            Expanded(
              child: Text(text, style: const TextStyle(color: AppColors.warning)),
            ),
          ],
        ),
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: DfCard(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.info_outline_rounded, color: AppColors.cyan),
            const SizedBox(width: 12),
            Expanded(
              child: Text(text, style: AppTextStyles.muted),
            ),
          ],
        ),
      ),
    );
  }
}
