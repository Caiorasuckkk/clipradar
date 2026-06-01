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
