import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

class ClipVideoPlayer extends StatefulWidget {
  const ClipVideoPlayer({super.key, required this.url});

  final String url;

  @override
  State<ClipVideoPlayer> createState() => _ClipVideoPlayerState();
}

class _ClipVideoPlayerState extends State<ClipVideoPlayer> {
  VideoPlayerController? _controller;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant ClipVideoPlayer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.url != widget.url) {
      _load();
    }
  }

  Future<void> _load() async {
    await _controller?.dispose();
    setState(() {
      _controller = null;
      _error = null;
    });
    try {
      final controller = VideoPlayerController.networkUrl(
        Uri.parse(widget.url),
      );
      await controller.initialize();
      controller.setLooping(true);
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() => _controller = controller);
    } catch (error) {
      if (mounted) setState(() => _error = error);
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    return Container(
      decoration: BoxDecoration(
        color: Colors.black,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.45),
            blurRadius: 32,
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: AspectRatio(
        aspectRatio: 16 / 9,
        child: Stack(
          fit: StackFit.expand,
          children: [
            if (_error != null)
              _VideoStateMessage(
                icon: Icons.error_outline_rounded,
                title: 'Erro ao carregar video',
                detail: 'Confira o IP do backend e tente novamente',
                color: const Color(0xFFEF4444),
                onTap: _load,
              )
            else if (controller == null)
              const _VideoStateMessage(
                icon: Icons.downloading_rounded,
                title: 'Carregando clipe',
                detail: 'Preparando player local',
                color: Color(0xFF00C8F0),
              )
            else
              FittedBox(
                fit: BoxFit.cover,
                child: SizedBox(
                  width: controller.value.size.width,
                  height: controller.value.size.height,
                  child: VideoPlayer(controller),
                ),
              ),
            if (controller != null) _Controls(controller: controller),
          ],
        ),
      ),
    );
  }
}

class _Controls extends StatefulWidget {
  const _Controls({required this.controller});

  final VideoPlayerController controller;

  @override
  State<_Controls> createState() => _ControlsState();
}

class _ControlsState extends State<_Controls> {
  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_refresh);
  }

  @override
  void didUpdateWidget(covariant _Controls oldWidget) {
    super.didUpdateWidget(oldWidget);
    oldWidget.controller.removeListener(_refresh);
    widget.controller.addListener(_refresh);
  }

  @override
  void dispose() {
    widget.controller.removeListener(_refresh);
    super.dispose();
  }

  void _refresh() {
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final value = controller.value;
    return Stack(
      children: [
        DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                Colors.transparent,
                Colors.black.withValues(alpha: 0.78),
              ],
            ),
          ),
          child: const SizedBox.expand(),
        ),
        Center(
          child: InkWell(
            onTap: () =>
                value.isPlaying ? controller.pause() : controller.play(),
            borderRadius: BorderRadius.circular(32),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 150),
              width: 62,
              height: 62,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: value.isPlaying
                    ? Colors.black.withValues(alpha: 0.35)
                    : const Color(0xFF00C8F0).withValues(alpha: 0.16),
                border: Border.all(color: const Color(0xFF00C8F0), width: 2),
              ),
              child: Icon(
                value.isPlaying
                    ? Icons.pause_rounded
                    : Icons.play_arrow_rounded,
                color: const Color(0xFF00C8F0),
                size: 34,
              ),
            ),
          ),
        ),
        Positioned(
          left: 12,
          right: 12,
          bottom: 10,
          child: Column(
            children: [
              VideoProgressIndicator(
                controller,
                allowScrubbing: true,
                colors: const VideoProgressColors(
                  playedColor: Color(0xFF00C8F0),
                  bufferedColor: Color(0x665B6478),
                  backgroundColor: Color(0x44FFFFFF),
                ),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  InkWell(
                    onTap: () => value.isPlaying
                        ? controller.pause()
                        : controller.play(),
                    child: Icon(
                      value.isPlaying
                          ? Icons.pause_rounded
                          : Icons.play_arrow_rounded,
                      color: const Color(0xFFE8EAF0),
                      size: 22,
                    ),
                  ),
                  const SizedBox(width: 8),
                  InkWell(
                    onTap: () => controller.seekTo(Duration.zero),
                    child: const Icon(
                      Icons.replay_rounded,
                      color: Color(0xFF9CA3AF),
                      size: 19,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    '${_time(value.position)} / ${_time(value.duration)}',
                    style: const TextStyle(
                      color: Color(0xFF9CA3AF),
                      fontSize: 11,
                    ),
                  ),
                  const Spacer(),
                  const Icon(
                    Icons.volume_up_rounded,
                    color: Color(0xFF9CA3AF),
                    size: 18,
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }

  String _time(Duration duration) {
    final minutes = duration.inMinutes;
    final seconds = duration.inSeconds % 60;
    return '$minutes:${seconds.toString().padLeft(2, '0')}';
  }
}

class _VideoStateMessage extends StatelessWidget {
  const _VideoStateMessage({
    required this.icon,
    required this.title,
    required this.detail,
    required this.color,
    this.onTap,
  });

  final IconData icon;
  final String title;
  final String detail;
  final Color color;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Container(
        color: const Color(0xFF08090E),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: color.withValues(alpha: 0.14),
                border: Border.all(color: color.withValues(alpha: 0.35)),
              ),
              child: Icon(icon, color: color),
            ),
            const SizedBox(height: 12),
            Text(
              title,
              style: const TextStyle(
                color: Color(0xFFE8EAF0),
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              detail,
              style: const TextStyle(color: Color(0xFF6B7280), fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }
}
