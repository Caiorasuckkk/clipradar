# ClipRadar

ClipRadar is a trend scanner for finding rising topics, validating related YouTube videos, and ranking opportunity signals.

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

## Future Scanner Run

The MVP scanner will be run from the backend package with:

```powershell
python -m app.jobs.run_scanner
```
