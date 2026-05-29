# ClipRadar

ClipRadar is a trend scanner for finding rising topics, validating related YouTube videos, and ranking opportunity signals.

MVP Scanner 0.3 collects trend signals from Google Trends, RSS news feeds, Google News RSS, and YouTube popular videos. It groups similar topics, validates the strongest opportunities against YouTube search, writes a ranked JSON report, and generates a human-readable opportunity report for review.

Google Trends can fail because the unofficial `pytrends` endpoint is unstable. When that happens, ClipRadar marks Google Trends fallback signals as mock data and penalizes them. The ranking now leans on alternative real sources, especially Google News RSS and YouTube popular videos.

Version 0.2.1 added `suitability_score`, a quality filter that reduces noise from music releases, loose artist names, generic terms, mock-only trends, and topics that are popular but not clearly useful for short-form explanatory content.

Version 0.3 adds the Opportunity Report: Markdown and JSON files with the best `produce` and `review` topics, related videos, score rationale, and suggested short-video angles.

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
APP_ENV=development
```

`YOUTUBE_API_KEY` is optional for local smoke tests. Without it, ClipRadar still runs Google Trends, RSS, and Google News RSS collection, but skips YouTube popular videos and YouTube search validation.

## Scanners

ClipRadar MVP 0.3 uses:

- `GoogleTrendsScanner`: tries Google Trends through `pytrends`; if it fails, emits explicitly marked mock fallback signals.
- `RSSNewsScanner`: reads configured news RSS feeds and extracts compact keywords from titles.
- `GoogleNewsRSSScanner`: searches Google News RSS for broad BR and global trend categories.
- `YouTubePopularScanner`: reads popular YouTube videos by region and turns their titles into trend signals.
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
