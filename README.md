# ClipRadar

ClipRadar is a trend scanner for finding rising topics, validating related YouTube videos, and ranking opportunity signals.

MVP Scanner 0.1 collects trend signals from Google Trends and RSS news feeds, groups similar topics, validates the strongest opportunities against YouTube, and writes a ranked JSON report.

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

`YOUTUBE_API_KEY` is optional for local smoke tests. Without it, ClipRadar still runs Google Trends and RSS collection, but skips YouTube video validation.

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
