# ClipRadar

ClipRadar is a trend scanner for finding rising topics, validating related YouTube videos, and ranking opportunity signals.

MVP Scanner collects trend signals from Google Trends fallback data, RSS news feeds, Google Trends RSS, and YouTube popular videos. It groups similar topics, validates the strongest opportunities against YouTube search, writes a ranked JSON report, and generates a human-readable opportunity report for review.

Google Trends can fail because the unofficial `pytrends` endpoint is unstable. When that happens, ClipRadar marks Google Trends fallback signals as mock data and penalizes them. The ranking now leans on alternative real sources, especially Google Trends RSS and YouTube popular videos.

Version 0.2.1 added `suitability_score`, a quality filter that reduces noise from music releases, loose artist names, generic terms, mock-only trends, and topics that are popular but not clearly useful for short-form explanatory content.

Version 0.3 adds the Opportunity Report: Markdown and JSON files with the best `produce` and `review` topics, related videos, score rationale, and suggested short-video angles.

Version 0.3.1 adds report-quality debugging. Each opportunity now includes evidence titles, source URLs, original grouped keywords, and debug notes so a human reviewer can understand why a topic ranked highly before any transcription or clipping work starts.

Version 0.3.2 adds the High Attention YouTube Radar. It prioritizes YouTube-native themes with stronger retention potential, including podcast clips, scandals, investigations, political and financial controversies, public figures, influencers, and international cases. The new `attention_score` and `attention_category` help separate high-attention review candidates from generic news. Risky topics must still be reviewed before publication.

Version 0.4.0 makes the High Attention Radar trend-first. Instead of relying only on static hand-written queries, it builds YouTube search queries from live trend sources and optional Reddit BR signals, then falls back to static queries only when dynamic sources are unavailable. It also softens score penalties when YouTube quota is exhausted, so strong trend signals do not collapse to `ignore` just because video validation was unavailable.

Version 0.4.1 replaces the broken `pytrends.trending_searches()` endpoint with YouTube Trending scraping and Google Trends RSS fallback. It also caches the last dynamic queries for up to 4 hours and supports multiple YouTube API keys through automatic quota rotation.

Version 0.4.2 removes Google News RSS from the ranking path because it returns random article headlines rather than search trends. It uses Google Trends RSS terms, adds stricter noise filtering, hides low-attention fragments from the Top 20, and makes `risk_score` react to political, crime, fraud, lawsuit, leak, and scandal triggers.

Version 0.4.3 improves BR relevance scoring, saves a small YouTube Trending HTML debug sample when title extraction fails, and adds degraded mode. When YouTube quota is exhausted, strong real-source topics can remain as `review` with `needs_youtube_validation` instead of disappearing as `ignore`.

Version 0.4.4 makes discovery dynamic. ClipRadar extracts entities from current trend evidence and generates podcast/interview/clip queries automatically, so examples like Banco Master, Epstein, or Diddy are only category examples, not fixed search strategy. When YouTube quota is unavailable, strong dynamic topics remain as `review`, never `produce`.

Version 0.4.5 adds source-first topic quality. `topic_base_quality_score` is calculated before query expansion, `expansion_allowed` blocks weak topics, and `dynamic_query_quality_score` is capped by the original topic quality. This prevents generic trends from becoming high-ranked just because the system appended words like podcast, interview, scandal, or escândalo.

The scanner now also tracks clip-rights signals. Creative Commons metadata and known official clip ecosystems can improve review priority, while large creators such as MrBeast remain `needs_permission_review` unless a video license or explicit permission is verified. This avoids treating popularity as permission.

Version 0.5.0 adds the Whisper Pipeline. Ranked videos are stored in a local queue, then `process_queue` downloads audio with `yt-dlp`, transcribes locally with Whisper, finds 30-60 second candidate clips with local heuristics, and writes clip JSON files. Whisper transcription is local; OpenAI is used only for optional title/hashtag metadata when `OPENAI_API_KEY` is configured.

Version 0.5.1 adds processing priority and queue cleanup. `engagement_score` still measures YouTube traction, while `processing_priority_score` decides what should be transcribed first. The priority score favors long podcasts/interviews with strong cut potential and rejects Shorts, very short videos, generic titles, and low-engagement items before Whisper spends time on them.

## Setup

Create a virtual environment:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create a local environment file from the example:

```powershell
Copy-Item .env.example .env
```

Fill in the required values in `.env`:

```text
YOUTUBE_API_KEY=
YOUTUBE_API_KEYS=
APP_ENV=development
TOP_TOPICS_TO_PROCESS=20
REPORT_TOP_N=20
VIDEOS_PER_TOPIC=5
HIGH_ATTENTION_QUERIES_PER_MARKET=6
ENABLE_HIGH_ATTENTION_SCANNER=true
WHISPER_MODEL_SIZE=base
MAX_VIDEOS_PER_RUN=5
OPENAI_API_KEY=
```

`YOUTUBE_API_KEY` is optional for local smoke tests. Without it, ClipRadar still runs RSS, Google Trends RSS, Google Trends fallback, and dynamic query discovery, but skips YouTube API validation. Use `YOUTUBE_API_KEYS=key2,key3` to add backup keys for quota rotation.

By default, the radar processes the Top 20 topics, includes up to 20 opportunities in the report, and fetches up to 5 related videos per topic. These values can be changed through `.env` with `TOP_TOPICS_TO_PROCESS`, `REPORT_TOP_N`, and `VIDEOS_PER_TOPIC`. Keep `VIDEOS_PER_TOPIC` at 5 or lower for the lightweight MVP flow.

The High Attention Radar is enabled by default. Use `ENABLE_HIGH_ATTENTION_SCANNER=false` to disable it, or tune `HIGH_ATTENTION_QUERIES_PER_MARKET` to control YouTube API quota usage.

## Scanners

ClipRadar MVP 0.3 uses:

- `GoogleTrendsScanner`: tries Google Trends through `pytrends`; if it fails, emits explicitly marked mock fallback signals.
- `RSSNewsScanner`: reads configured news RSS feeds and extracts compact keywords from titles.
- `GoogleNewsRSSScanner`: kept as a compatibility class name, but now reads Google Trends RSS terms instead of Google News RSS headlines.
- `YouTubePopularScanner`: reads popular YouTube videos by region and turns their titles into trend signals.
- `YouTubeHighAttentionScanner`: searches limited high-attention YouTube queries for podcasts, scandals, investigations, political/financial cases, and viral controversy signals.
- `TrendQueryBuilder`: builds dynamic high-attention queries from YouTube Trending HTML, Google Trends RSS, and optional Reddit BR sources before falling back to cached or static query lists.
- `YouTubeScanner`: validates top ranked topics by searching related videos.

## Run Scanner

Run from the backend directory:

```powershell
cd backend
python -m app.jobs.run_scanner
```

Results are saved to:

```text
backend/app/storage/trends/results_YYYYMMDD_HHMM.json
```

Opportunity reports are saved to:

```text
backend/app/storage/reports/opportunity_report_YYYYMMDD_HHMM.md
backend/app/storage/reports/opportunity_report_YYYYMMDD_HHMM.json
```

These reports are intended for human review before any future transcription, clipping, or publishing workflow.

## Process Queue

After running the scanner, videos from `produce` and `review` topics are saved with status `queued` in local storage. Process the queue from the backend directory:

```powershell
python -m app.jobs.process_queue
```

Clean the queue before processing:

```powershell
python -m app.jobs.cleanup_queue
python -m app.jobs.review_selected_videos
```

`cleanup_queue` marks weak queued videos as `rejected_queue`, including Shorts, videos shorter than 120 seconds, generic titles, and videos with `engagement_score < 5`. `process_queue` then uses `processing_priority_score`, not insertion order, so long podcasts and interviews such as TICARACATICAST, Flow, Podpah, Inteligência Ltda, Papo de Elite, and similar formats are processed first.

Generated files:

```text
backend/app/storage/transcripts/{video_id}.json
backend/app/storage/clips/{video_id}_clips.json
```

Audio downloads are temporary and are removed after transcription. If a transcript already exists, ClipRadar reuses the cache and does not download/transcribe again. Without `OPENAI_API_KEY`, clip metadata uses local placeholders instead of paid API calls.

## Manual Clip Review

Generated clips start as `pending_review`. ClipRadar does not import old feedback automatically and does not turn previous examples into training data. Feedback is saved only when you run the manual review command.

Review a clip:

```powershell
python -m app.jobs.review_clip --video-id VIDEO_ID --rank 1 --status approved --rating 4 --reason "bom"
```

Review a diagnostic candidate:

```powershell
python -m app.jobs.review_clip --video-id VIDEO_ID --target diagnostic --rank 3 --status approved --rating 4 --reason "bom"
```

Statuses:

- `approved`: the clip is good.
- `rejected`: the clip is bad or unusable.
- `needs_adjustment`: the idea is good, but start/end should move.

For boundary fixes, pass ideal timestamps:

```powershell
python -m app.jobs.review_clip --video-id VIDEO_ID --rank 1 --status needs_adjustment --rating 3 --reason "terminou cedo" --ideal-start 345.0 --ideal-end 402.0
```

List clips awaiting review:

```powershell
python -m app.jobs.list_pending_reviews
```

Export the reviewed-only dataset:

```powershell
python -m app.jobs.export_feedback_dataset
```

The dataset includes only `approved`, `rejected`, and `needs_adjustment` clips. `pending_review` clips are excluded. Future analyzer improvements can use `ideal_start_seconds` and `ideal_end_seconds` as correction labels.

Diagnostic candidates are included in the exported dataset when manually reviewed. Each record includes `source_collection` as either `clips` or `diagnostic_candidates`, so calibration can distinguish recommended clips from rejected candidates that later proved useful.

## Cuttable Format Discovery Batch

Use the discovery batch to find fresh long-form and medium-form videos with short-clip potential without downloading or transcribing anything:

```powershell
python -m app.jobs.discover_podcast_batch
python -m app.jobs.review_selected_videos
python -m app.jobs.process_queue
```

The discovery job searches recent BR and global cuttable-format queries with YouTube API key rotation. Eligible formats include podcasts/interviews, conversation shows, story-driven segments, travel/storytelling, opinion/debate, backstage material, personal accounts, and narrative analysis. It filters out Shorts, gameplay, music videos, trailers, weak fan clips, low-originality reacts, local/institutional material, news snippets without conversation, and short videos below the configured minimum. By default it keeps videos at least 8 minutes long, limits each channel to 3 videos, calculates `processing_priority_score`, values editorial buckets such as podcast/interview, humor/famous, football, business/money, politics/opinion, travel/storytelling, and science/behavior, then queues selected videos for later processing.

Discovery settings can be tuned in `.env`:

```text
PODCAST_DISCOVERY_ENABLED=true
PODCAST_DISCOVERY_MAX_RESULTS=30
PODCAST_DISCOVERY_DAYS_BACK=14
PODCAST_DISCOVERY_MIN_DURATION_SECONDS=480
PODCAST_DISCOVERY_MAX_PER_CHANNEL=3
PODCAST_DISCOVERY_MARKETS=BR,GLOBAL
```

Reports are written to:

```text
backend/app/storage/reports/podcast_discovery_report_YYYYMMDD_HHMM.md
backend/app/storage/reports/podcast_discovery_report_YYYYMMDD_HHMM.json
```

## ClipRadar 0.5.19 - Export Approved Clips Plan

Export a JSON and Markdown plan with manually approved clips that are ready for a later FFmpeg cutting step:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.export_approved_clips_plan
```

This does not generate videos, download media, transcribe audio, or call external AI. It only reads existing `*_clips.json` review data and prepares `approved_clips_plan_YYYYMMDD_HHMM` files in `backend/app/storage/reports`.

## ClipRadar 0.5.20 - FFmpeg Clip Renderer

Render approved clips from the latest approved clips plan:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.render_approved_clips --dry-run --limit 1
.\.ven\Scripts\python.exe -m app.jobs.render_approved_clips --limit 1
.\.ven\Scripts\python.exe -m app.jobs.render_approved_clips --video-id Jc9Ydqmjcew --rank 2
```

The renderer reads `approved_clips_plan_*.json`, uses `final_start_seconds` and `final_end_seconds`, and writes raw horizontal `.mp4` clips to `backend/app/storage/exports`. It does not create vertical edits, subtitles, thumbnails, or publications.

### ClipRadar 0.5.20.1 - Download Missing Source

By default, missing source videos are still reported as `missing_source`. To allow the renderer to fetch the source video with `yt-dlp` only when needed, pass `--download-missing`:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.render_approved_clips --video-id Sfg2S4DEGo0 --rank 1 --download-missing --overwrite
```

This downloads the source to `backend/app/storage/videos/{video_id}.mp4`, then renders the approved clip. It does not run Whisper, transcribe, call OpenAI, or publish anything.

## ClipRadar 0.5.21 - Local Review API

Start the local API from the backend directory:

```powershell
.\.ven\Scripts\python.exe -m app.main
```

The API lists rendered `.mp4` clips from `backend/app/storage/exports`, serves them locally, and saves manual swipe-style reviews to `backend/app/storage/reviews/rendered_clip_reviews.json`. It does not download media, render clips, run Whisper, call OpenAI, or publish anything.

Endpoints:

```text
GET  /review/clips
GET  /review/clips/next
GET  /review/clips/{clip_id}
GET  /exports/{filename}
POST /review/clips/{clip_id}
GET  /review/summary
```

Example review:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/review/clips/Jc9Ydqmjcew__rank_2__rating_5__otimo__2216_2270" -ContentType "application/json" -Body '{"status":"approved","rating":5,"reason":"otimo","notes":"Corte aprovado no app local","ideal_start_seconds":null,"ideal_end_seconds":null}'
```

Export rendered reviews for future dataset integration:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.export_rendered_reviews_dataset
```

## ClipRadar 0.5.23 - Sync Rendered Reviews into Feedback Calibration

Reviews made in the local review app are saved to `backend/app/storage/reviews/rendered_clip_reviews.json` and are now included in the regular feedback dataset export. They appear with `source_collection=rendered_clip_reviews` and `feedback_origin=rendered_app_review`, so the analyzer can learn from reviews made against the rendered `.mp4` clips while keeping terminal reviews separate.

```powershell
.\.ven\Scripts\python.exe -m app.jobs.export_feedback_dataset
.\.ven\Scripts\python.exe -m app.jobs.analyze_feedback_dataset
.\.ven\Scripts\python.exe -m app.jobs.list_rendered_reviews
.\.ven\Scripts\python.exe -m app.jobs.list_rendered_reviews --reason teste_api
```

Rendered app reviews are enriched from the latest `approved_clips_plan_*.json` when possible, including title, rank, timestamps, YouTube URL, source quality, ranking quality, sponsor/product score, and topic merge score. If a review with reason `teste_api` is present, `analyze_feedback_dataset` prints a warning before calibration.

## ClipRadar 0.5.24 - Review App Polish + Queue Controls

The Flutter review app now has a more comfortable queue workflow for reviewing many rendered clips. It shows a compact summary, queue counts, filters for pending/reviewed/all clips, a session-only skip list, a reviewed clips history, review editing, required rating/status/reason validation, safer save loading states, and an `Abrir YouTube` action for the original video URL.

Start the local API:

```powershell
cd backend
.\.ven\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Run on a real Android device over USB:

```powershell
cd review_app
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb reverse tcp:8000 tcp:8000
flutter run -d 4eb16e24 --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Reviews continue to be saved in `backend/app/storage/reviews/rendered_clip_reviews.json`. The app does not download, render, transcribe, publish, or call external AI.

## ClipRadar 0.5.25 - Vertical 9:16 Renderer

Generate simple vertical versions of already rendered clips:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.render_vertical_clips --dry-run --limit 1
.\.ven\Scripts\python.exe -m app.jobs.render_vertical_clips --limit 1
.\.ven\Scripts\python.exe -m app.jobs.render_vertical_clips --video-id Jc9Ydqmjcew --overwrite
```

The job reads `.mp4` files from `backend/app/storage/exports` and writes 1080x1920 vertical files to `backend/app/storage/vertical_exports`. The layout uses the clip itself as a blurred darkened background, with the original video centered sharply in front. It preserves audio and exports h264/aac with `+faststart`.

This step does not add subtitles, titles, logos, captions, publishing, downloads, Whisper, OpenAI, or YouTube rendering.

## ClipRadar 0.5.26 - Subtitle Burn-in Renderer

Burn simple segment-based subtitles into vertical clips:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.render_subtitled_clips --dry-run --limit 1
.\.ven\Scripts\python.exe -m app.jobs.render_subtitled_clips --limit 1
.\.ven\Scripts\python.exe -m app.jobs.render_subtitled_clips --video-id Jc9Ydqmjcew --overwrite
```

The job reads `backend/app/storage/vertical_exports/*.mp4`, finds the matching existing transcript in `backend/app/storage/transcripts/{video_id}.json`, generates an `.ass` subtitle file in `backend/app/storage/subtitles`, and writes the burned-in result to `backend/app/storage/subtitled_exports`.

Subtitles are simple transcript-segment blocks, wrapped to short two-line captions. This is not word-by-word captioning yet, and it does not use Whisper, OpenAI, downloads, YouTube rendering, titles, logos, or publishing.

### ClipRadar 0.5.26.1 - Clip-level Subtitle Transcription

For better final subtitles, transcribe only the short rendered clips from `backend/app/storage/exports` with a stronger local Whisper model:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.transcribe_rendered_clips --dry-run --limit 1
.\.ven\Scripts\python.exe -m app.jobs.transcribe_rendered_clips --limit 1 --model base --language pt
.\.ven\Scripts\python.exe -m app.jobs.transcribe_rendered_clips --video-id Jc9Ydqmjcew --overwrite --model base --language pt
```

Then regenerate burned-in subtitles:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.render_subtitled_clips --video-id Jc9Ydqmjcew --overwrite --limit 2
```

Clip transcripts are saved to `backend/app/storage/clip_transcripts/{clip_id}.json` with relative timestamps. `render_subtitled_clips` prefers those clip-level transcripts when available, then falls back to the older full-video transcripts. This improves subtitle text without retranscribing long podcasts and without using OpenAI, downloads, or publishing.

### ClipRadar 0.5.26.2 - Subtitle Timing QA and Accuracy Fix

Validate clip-level subtitle timing and regenerate subtitles with an optional manual offset:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.transcribe_rendered_clips --video-id Jc9Ydqmjcew --limit 1 --model small --language pt --overwrite --print-text
.\.ven\Scripts\python.exe -m app.jobs.inspect_clip_subtitle_sync --video-id Jc9Ydqmjcew
.\.ven\Scripts\python.exe -m app.jobs.render_subtitled_clips --video-id Jc9Ydqmjcew --limit 1 --overwrite
.\.ven\Scripts\python.exe -m app.jobs.render_subtitled_clips --video-id Jc9Ydqmjcew --limit 1 --overwrite --subtitle-offset -0.5
```

The transcriber now records clip duration, transcript duration, segment counts, first/last timestamps, model/language used, and flags suspected absolute timestamps. `render_subtitled_clips` prints the transcript source before rendering, uses `clip_transcripts` exclusively when present, keeps clip transcript timestamps relative to the final video, and writes timing warnings/errors into the subtitle report. `inspect_clip_subtitle_sync` compares export, vertical, subtitled, transcript, and ASS files without downloading, using YouTube, OpenAI, or retranscribing long videos.

## ClipRadar 0.5.27 - Clean Final Export

Generate clean final files from already vertical clips:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.render_final_clips --dry-run --limit 1
.\.ven\Scripts\python.exe -m app.jobs.render_final_clips --limit 1 --overwrite
.\.ven\Scripts\python.exe -m app.jobs.render_final_clips --video-id Jc9Ydqmjcew --overwrite
```

The job reads `backend/app/storage/vertical_exports/*.mp4` and writes final 1080x1920 files to `backend/app/storage/final_exports`. The final export is intentionally clean: no identity overlay, subtitles, badge, logo, brand text, or progress bar. By default it uses stream copy/remux to preserve quality, with `--reencode` available when h264/aac output needs to be forced. It does not run Whisper, call OpenAI, download media, use YouTube, publish, or touch the analyzer.

## ClipRadar 0.5.28 - Final Clip Metadata + Final Review Queue

Export metadata for clean final clips and review them before manual posting:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.export_final_clips_metadata
```

The job reads `backend/app/storage/final_exports/*.mp4`, enriches each item from the latest approved clips plan and rendered clip reviews, and writes `final_clips_metadata_YYYYMMDD_HHMM` JSON/Markdown reports. It does not use FFmpeg rendering, Whisper, OpenAI, downloads, YouTube, or publishing.

Final review API:

```text
GET  /final/clips
GET  /final/clips/next
GET  /final/clips/{final_clip_id}
GET  /final_exports/{filename}
POST /final/clips/{final_clip_id}
GET  /final/summary
```

Final reviews are saved in `backend/app/storage/final_reviews/final_clip_reviews.json` with statuses `ready_to_post`, `do_not_post`, and `needs_edit`. The Flutter review app now has a second tab, `Final Clips`, for watching final exports and marking which clips are ready for posting.

## ClipRadar 0.5.29 - Ready-to-Post Package Export

Create a manual posting package with only final clips marked as `ready_to_post`:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.export_ready_to_post_package --dry-run
.\.ven\Scripts\python.exe -m app.jobs.export_ready_to_post_package
```

The job reads `backend/app/storage/final_exports` plus `backend/app/storage/final_reviews/final_clip_reviews.json`, copies only approved final clips into `backend/app/storage/posting_package/YYYYMMDD_HHMM/videos`, and writes package-level JSON/Markdown plus individual metadata files. It does not publish automatically and does not use OpenAI, Whisper, FFmpeg, downloads, YouTube, or rendering.

## ClipRadar 0.5.30 - Pipeline Command Orchestrator

Run the ready-to-post preparation pipeline from one command:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.pipeline_ready_to_post --dry-run --limit 1
.\.ven\Scripts\python.exe -m app.jobs.pipeline_ready_to_post --limit 1 --download-missing --overwrite --package-name test_pipeline
.\.ven\Scripts\python.exe -m app.jobs.pipeline_ready_to_post --download-missing --overwrite
```

The pipeline executes the existing jobs in order: approved plan export, approved clip render, vertical render, clean final export, final metadata export, and ready-to-post package export. It does not publish, does not use OpenAI or Whisper, and does not run the subtitle pipeline. Start with `--dry-run --limit 1` to inspect the commands before running actual rendering/copying.

## ClipRadar 0.5.31 - Candidate Preview Queue for Mobile Review

Generate a mobile review queue for newly processed candidates:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.export_candidate_review_queue --video-id IKFMtoU9TGE,lJ3nef7UvLM,D7CpjXX4Voc --include-diagnostics --overwrite
.\.ven\Scripts\python.exe -m app.jobs.render_candidate_previews --download-missing --overwrite
```

### ClipRadar 0.5.31.1 - Candidate Preview Availability Gate

The candidate API now returns only candidates whose local preview `.mp4` exists by default. This prevents the Android player from opening `/candidate_previews/...` URLs that would return 404. Use `include_missing_previews=true` only for diagnostics.

Recommended flow:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.export_candidate_review_queue --video-id IKFMtoU9TGE,lJ3nef7UvLM,D7CpjXX4Voc --include-diagnostics --overwrite
.\.ven\Scripts\python.exe -m app.jobs.list_candidate_preview_status --missing-only
.\.ven\Scripts\python.exe -m app.jobs.render_candidate_previews --only-missing --download-missing --overwrite
.\.ven\Scripts\python.exe -m app.jobs.render_candidate_previews --only-missing --download-missing --overwrite --max-missing 5
```

`GET /candidate/clips?status=pending` and `GET /candidate/clips/next` now skip missing previews. `GET /candidate/clips?status=pending&include_missing_previews=true` includes them for inspection. `GET /candidate/summary` reports `preview_ready` and `missing_preview`.

Candidate reviews are saved in `backend/app/storage/candidate_reviews/candidate_clip_reviews.json` through the local API:

```text
GET  /candidate/clips
GET  /candidate/clips/next
GET  /candidate/clips/{candidate_id}
GET  /candidate_previews/{filename}
POST /candidate/clips/{candidate_id}
GET  /candidate/summary
```

The Android review app now has a `Candidate Clips` tab for previewing recommended clips and diagnostic candidates, then saving `approved`, `rejected`, or `needs_adjustment` feedback. Candidate mobile reviews are included in `export_feedback_dataset`, surfaced in `analyze_feedback_dataset`, and approved candidates with rating >= 4 are included by `export_approved_clips_plan`.

Run the app locally:

```powershell
adb reverse tcp:8000 tcp:8000
flutter run -d 4eb16e24 --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

## ClipRadar 0.5.32 - Batch Status + Retry + Cleanup

Use the batch status and retry tools to operate local review batches without guessing which step is stale:

```powershell
.\.ven\Scripts\python.exe -m app.jobs.batch_status
.\.ven\Scripts\python.exe -m app.jobs.list_candidate_preview_status --missing-only
.\.ven\Scripts\python.exe -m app.jobs.render_candidate_previews --only-missing --download-missing --overwrite --max-missing 5
.\.ven\Scripts\python.exe -m app.jobs.list_failed_candidate_downloads
.\.ven\Scripts\python.exe -m app.jobs.render_candidate_previews --retry-failed --download-missing --overwrite --clean-partials
.\.ven\Scripts\python.exe -m app.jobs.export_ready_to_post_package --package-name latest
.\.ven\Scripts\python.exe -m app.jobs.export_ready_to_post_package --clean-old
```

`batch_status` summarizes candidate queue health, preview availability, review counts, rendered exports, final review counts, the latest posting package, recent reports, and tracked failed downloads. Candidate preview downloads now retry with simple backoff, can clean `.part`/`.ytdl` files for selected videos, and write failures to `backend/app/storage/reports/failed_candidate_downloads.json`. `export_ready_to_post_package --package-name latest` writes a stable `posting_package/latest` folder, while `--clean-old` removes old package folders safely inside `backend/app/storage/posting_package`.

## Reference Clip Benchmark

ClipRadar keeps a small local benchmark of Shorts the user considers good editorial references:

```text
backend/app/storage/reference/reference_good_clips.json
```

These links are not downloaded and are not copied. They are used only as a manual benchmark to calibrate what a good podcast cut should feel like: strong hook, clear context, complete thought, good pacing, no filler, clean ending, standalone value, and curiosity or emotion.

List reference clips:

```powershell
python -m app.jobs.list_reference_clips
```

Update a reference manually:

```powershell
python -m app.jobs.update_reference_clip --url "https://www.youtube.com/shorts/K8lDjkwrRQY" --strong-hook true --clear-context true --complete-thought true --good-pacing true --clear-ending true --viral-potential 5 --notes "Referência de bom corte"
```

Generated clips now include `reference_alignment_score`, a heuristic score that estimates whether a candidate resembles the benchmark pattern. It does not override the stricter recommendation rules; weak clips can still remain diagnostic-only.
