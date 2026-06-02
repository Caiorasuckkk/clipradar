import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../models/candidate_clip.dart';
import '../models/candidate_summary.dart';
import '../widgets/clip_video_player.dart';
import '../widgets/rating_stars.dart';
import '../widgets/reason_chips.dart';
import '../widgets/status_buttons.dart';

enum CandidateFilter { pending, reviewed, all }

class CandidateClipsScreen extends StatefulWidget {
  const CandidateClipsScreen({super.key});

  @override
  State<CandidateClipsScreen> createState() => _CandidateClipsScreenState();
}

class _CandidateClipsScreenState extends State<CandidateClipsScreen> {
  final ApiClient _api = ApiClient();
  final TextEditingController _notesController = TextEditingController();

  CandidateSummary? _summary;
  List<CandidateClip> _clips = [];
  CandidateClip? _clip;
  CandidateFilter _filter = CandidateFilter.pending;
  bool _loading = true;
  bool _saving = false;
  String? _error;
  int? _rating;
  String? _status;
  String _reason = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final summary = await _api.fetchCandidateSummary();
      final clips = await _api.fetchCandidateClips(
        status: _statusQuery(_filter),
      );
      if (!mounted) return;
      setState(() {
        _summary = summary;
        _clips = clips;
        _clip = clips.isEmpty ? null : clips.first;
        _loading = false;
      });
      _fillForm(_clip);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _loading = false;
      });
    }
  }

  String _statusQuery(CandidateFilter filter) {
    return switch (filter) {
      CandidateFilter.pending => 'pending',
      CandidateFilter.reviewed => 'reviewed',
      CandidateFilter.all => 'all',
    };
  }

  void _fillForm(CandidateClip? clip) {
    final review = clip?.currentReview;
    _notesController.text = review?.notes ?? '';
    _rating = review?.rating;
    _status = review?.status.isNotEmpty == true ? review!.status : null;
    _reason = review?.reason ?? '';
  }

  Future<void> _saveAndNext() async {
    final clip = _clip;
    if (clip == null || _saving) return;
    if (_rating == null || _status == null || _reason.trim().isEmpty) {
      _snack('Escolha nota, status e motivo.');
      return;
    }
    setState(() => _saving = true);
    try {
      await _api.saveCandidateReview(
        candidateId: clip.candidateId,
        status: _status!,
        rating: _rating!,
        reason: _reason.trim(),
        notes: _notesController.text.trim(),
      );
      final summary = await _api.fetchCandidateSummary();
      final clips = await _api.fetchCandidateClips(
        status: _statusQuery(_filter),
      );
      if (!mounted) return;
      setState(() {
        _summary = summary;
        _clips = clips;
        _clip = clips.isEmpty ? null : clips.first;
        _saving = false;
      });
      _fillForm(_clip);
      _snack('Review do candidato salva.');
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _saving = false;
      });
    }
  }

  void _snack(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            _Header(
              summary: _summary,
              filter: _filter,
              onRefresh: _load,
              onFilterChanged: (filter) {
                setState(() => _filter = filter);
                _load();
              },
            ),
            Expanded(child: _body()),
            if (_clip != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 10, 14, 16),
                child: SizedBox(
                  width: double.infinity,
                  height: 56,
                  child: FilledButton.icon(
                    onPressed: _saving ? null : _saveAndNext,
                    icon: const Icon(Icons.skip_next_rounded),
                    label: Text(_saving ? 'Salvando...' : 'Salvar e proximo'),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _body() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null && _clips.isEmpty) return Center(child: Text(_error!));
    final clip = _clip;
    if (clip == null) {
      return Center(
        child: Text(
          _filter == CandidateFilter.pending
              ? 'Nenhum candidato pronto. Volte para Operations e renderize previews.'
              : 'Sem candidatos',
          textAlign: TextAlign.center,
        ),
      );
    }
    return ListView(
      padding: const EdgeInsets.all(14),
      children: [
        if (clip.previewInvalid || clip.previewMissing || !clip.previewExists)
          const _MissingPreviewCard()
        else
          ClipVideoPlayer(
            url: _api.candidatePreviewUrl(clip.outputPreviewFilename),
          ),
        const SizedBox(height: 12),
        _InfoCard(clip: clip),
        const SizedBox(height: 12),
        RatingStars(
          value: _rating ?? 0,
          onChanged: (value) => setState(() => _rating = value),
        ),
        const SizedBox(height: 12),
        StatusButtons(
          value: _status ?? '',
          onChanged: (value) => setState(() => _status = value),
        ),
        const SizedBox(height: 12),
        ReasonChips(
          selected: _reason,
          onChanged: (value) => setState(() => _reason = value),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _notesController,
          minLines: 3,
          maxLines: 5,
          decoration: const InputDecoration(
            labelText: 'Notes opcionais',
            filled: true,
          ),
        ),
      ],
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.summary,
    required this.filter,
    required this.onRefresh,
    required this.onFilterChanged,
  });

  final CandidateSummary? summary;
  final CandidateFilter filter;
  final VoidCallback onRefresh;
  final ValueChanged<CandidateFilter> onFilterChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      color: const Color(0xFF0F1018),
      child: Column(
        children: [
          Row(
            children: [
              const Icon(Icons.preview_rounded, color: Color(0xFF00C8F0)),
              const SizedBox(width: 10),
              const Expanded(
                child: Text(
                  'Candidate Clips',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
                ),
              ),
              IconButton(
                onPressed: onRefresh,
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          Wrap(
            spacing: 12,
            children: [
              Text('Total ${summary?.totalCandidates ?? 0}'),
              Text('Prontos ${summary?.previewReady ?? 0}'),
              Text('Faltam ${summary?.missingPreview ?? 0}'),
              Text('Pend. ${summary?.pending ?? 0}'),
              Text('Ok ${summary?.approved ?? 0}'),
              Text('No ${summary?.rejected ?? 0}'),
            ],
          ),
          const SizedBox(height: 8),
          SegmentedButton<CandidateFilter>(
            segments: const [
              ButtonSegment(
                value: CandidateFilter.pending,
                label: Text('Pend.'),
              ),
              ButtonSegment(
                value: CandidateFilter.reviewed,
                label: Text('Rev.'),
              ),
              ButtonSegment(value: CandidateFilter.all, label: Text('Todos')),
            ],
            selected: {filter},
            onSelectionChanged: (value) => onFilterChanged(value.first),
          ),
        ],
      ),
    );
  }
}

class _MissingPreviewCard extends StatelessWidget {
  const _MissingPreviewCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFF171923),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFF34394A)),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.video_file_outlined, color: Color(0xFF00C8F0)),
          SizedBox(height: 10),
          Text(
            'Preview ainda não renderizado',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
          ),
          SizedBox(height: 6),
          Text(
            'Preview inválido ou ainda não renderizado. Gere o preview novamente em Operations.',
          ),
        ],
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({required this.clip});

  final CandidateClip clip;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1018),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            clip.videoTitle,
            style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 10),
          Text('candidate_id: ${clip.candidateId}'),
          Text('collection: ${clip.sourceCollection} rank ${clip.rank ?? '-'}'),
          Text('tempo: ${clip.timeRange}'),
          Text('reason: ${clip.reason.isEmpty ? '-' : clip.reason}'),
        ],
      ),
    );
  }
}
