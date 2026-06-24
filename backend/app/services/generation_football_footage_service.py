"""Semi-automatic football footage source.

Searches YouTube for highlight footage matching a query, downloads a couple of
short clips, and cuts them into a few short segments that the generation
pipeline can use as b-roll — the same role Pexels plays for generic stock, but
for real football footage (named players/teams) that stock libraries don't have.

IMPORTANT — copyright: broadcast football footage is owned by leagues/
broadcasters. This pulls public clips for repurposing, which lives in the same
grey zone as channels like @fut_m0ments4: tolerated by platforms until a claim/
strike lands. Treat the channel that uses it as disposable. This module only
exists because the "football drama" niche depends on entity-specific footage
that no licensed stock source provides.

Results are returned in the same dict shape as the stock-media services so the
asset layer can score/apply them — except `media_path` is already set to a local
file (no HTTP download needed).
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import imageio_ffmpeg

from app import config

FOOTBALL_DIR = config.STORAGE_GENERATION_DIR / "football"
SOURCES_DIR = FOOTBALL_DIR / "sources"
CLIPS_DIR = FOOTBALL_DIR / "clips"
# yt-dlp wants an executable literally named ffmpeg(.exe); imageio ships it under
# a versioned name, so expose a stable copy in a dir we can hand to yt-dlp.
_BIN_DIR = FOOTBALL_DIR / "_bin"

_VIDEO_EXT = ".mp4"


def _ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


_js_runtime_ready = False


def _ensure_js_runtime() -> bool:
    """Make `deno` reachable so yt-dlp can run YouTube's JS challenge and hand out
    HD (720p+) formats. winget installs deno outside the default PATH, so we find
    it and prepend its dir to PATH for this process. Returns True if available."""
    global _js_runtime_ready
    if _js_runtime_ready:
        return True
    if shutil.which("deno"):
        _js_runtime_ready = True
        return True
    home = os.path.expanduser("~")
    local = os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local"))
    patterns = [
        os.path.join(local, "Microsoft", "WinGet", "Packages", "DenoLand.Deno_*", "deno.exe"),
        os.path.join(local, "Microsoft", "WinGet", "Links", "deno.exe"),
        os.path.join(home, ".deno", "bin", "deno.exe"),
        os.path.join(home, ".deno", "bin", "deno"),
    ]
    import glob
    for pattern in patterns:
        for match in glob.glob(pattern):
            if os.path.isfile(match):
                os.environ["PATH"] = os.path.dirname(match) + os.pathsep + os.environ.get("PATH", "")
                _js_runtime_ready = True
                return True
    return False


def _ffmpeg_dir_for_ytdlp() -> str:
    _BIN_DIR.mkdir(parents=True, exist_ok=True)
    target = _BIN_DIR / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if not target.exists():
        shutil.copy2(_ffmpeg(), target)
    return str(_BIN_DIR)


def _key(text: str) -> str:
    return hashlib.md5((text or "").strip().lower().encode("utf-8")).hexdigest()[:16]


def search_football_clips(
    query: str,
    want: int = 12,
    seg_seconds: float = 5.0,
    max_sources: int = 4,
    max_source_duration: int = 720,
    subject_stem: str = "",
) -> list[dict[str, Any]]:
    """Return up to `want` local clip results for `query`. Cached per query.

    `subject_stem` (e.g. "mbapp") biases the YouTube search to videos whose TITLE
    mentions the player, so we segment clips actually about the subject instead of
    generic team compilations."""
    query = (query or "").strip()
    if not query:
        return []
    out_dir = CLIPS_DIR / _key(query)
    cached = _clip_results(out_dir, query)
    if cached:
        return cached[:want]

    sources = _download_sources(query, max_sources, max_source_duration, subject_stem)
    if not sources:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    for src in sources:
        _segment(src, out_dir, seg_seconds)
        if len(list(out_dir.glob(f"*{_VIDEO_EXT}"))) >= want * 2:
            break
    return _clip_results(out_dir, query)[:want]


def list_cached_clips(label: str = "football", limit: int = 80) -> list[dict[str, Any]]:
    """Every clip already downloaded this run, across all query folders — used as
    a last-resort pool so a football-mode segment whose specific search failed
    still gets REAL football footage instead of an off-topic stock/AI image."""
    if not CLIPS_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for folder in CLIPS_DIR.iterdir():
        if folder.is_dir():
            out.extend(_clip_results(folder, label))
            if len(out) >= limit:
                break
    return out[:limit]


def _download_sources(query: str, count: int, max_duration: int, subject_stem: str = "") -> list[Path]:
    try:
        import yt_dlp
    except Exception:
        return []
    has_deno = _ensure_js_runtime()  # unlock HD formats via deno when available
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    # Best video up to 1080p (render drops audio anyway); falls back to whatever
    # YouTube serves (360p when no PO token / HD formats are gated).
    fmt = "bestvideo[ext=mp4][height<=1080]/bestvideo[height<=1080]/best[ext=mp4]/best"
    # HD (720p+) formats now require a PO token; the practical way to get one is
    # cookies from a browser logged into YouTube. Opt-in (never read silently):
    # set GENERATION_FOOTBALL_COOKIES_BROWSER=edge|chrome|firefox. Without it,
    # quality is capped at 360p even with deno.
    cookies_browser = (os.environ.get("GENERATION_FOOTBALL_COOKIES_BROWSER") or "").strip().lower()

    def _run(filter_expr: str) -> list[Path]:
        opts: dict[str, Any] = {
            "format": fmt,
            "outtmpl": str(SOURCES_DIR / "%(id)s.%(ext)s"),
            "noplaylist": True,
            "ignoreerrors": True,
            "quiet": True,
            "no_warnings": True,
            "ffmpeg_location": _ffmpeg_dir_for_ytdlp(),
            "match_filter": yt_dlp.utils.match_filter_func(filter_expr),
            # web client + deno EJS solver = JS challenges solved (no 403s);
            # android/ios as fallback. EJS download is enabled so deno is used.
            "extractor_args": {"youtube": {"player_client": ["web", "android", "ios"]}},
            "retries": 3,
            "fragment_retries": 3,
        }
        if has_deno:
            opts["remote_components"] = ["ejs:github"]
        if cookies_browser:
            opts["cookiesfrombrowser"] = (cookies_browser,)
        # Search extra candidates so the title filter has room to reject mismatches.
        search = f"ytsearch{max(count * 4, count)}:{query}"
        paths: list[Path] = []
        seen: set[str] = set()
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(search, download=True)
        except Exception:
            return []
        entries = (info or {}).get("entries") or ([info] if info else [])
        for entry in entries:
            if not entry:
                continue
            vid = str(entry.get("id") or "")
            if not vid or vid in seen:
                continue
            candidate = SOURCES_DIR / f"{vid}{_VIDEO_EXT}"
            if candidate.exists() and candidate.stat().st_size > 4096:
                seen.add(vid)
                paths.append(candidate)
            if len(paths) >= count:
                break
        return paths

    # Exclude cartoons/animations/parodies (a title match on the player name also
    # hits animated series), and prefer short clips whose TITLE mentions the player
    # (more likely to be actually that player, not a mixed compilation). Fall back
    # to a generic short-clip search if the title filter finds nothing.
    base = (
        f"duration > 5 & duration < {int(max_duration)} "
        "& title !~= '(?i)(desenho|cartoon|cartum|anima|parodia|paródia|emoji|minecraft|fifa|efootball|pes20)'"
    )
    stem = re.sub(r"[^a-z]", "", (subject_stem or "").lower())[:6]
    if stem:
        paths = _run(f"{base} & title ~= '(?i){stem}'")
        if paths:
            return paths
    return _run(base)


def _segment(src: Path, out_dir: Path, seg_seconds: float) -> list[Path]:
    """Cut `src` into `seg_seconds` clips, skipping the first/last second.
    Stream-copy for speed; the final render re-encodes anyway."""
    width, height, duration = _probe(src)
    if duration <= 2:
        return []
    seg_seconds = max(2.0, float(seg_seconds))
    made: list[Path] = []
    start = 1.0
    index = 0
    while start + seg_seconds <= max(duration - 1.0, seg_seconds):
        index += 1
        dest = out_dir / f"{src.stem}_{index:03d}{_VIDEO_EXT}"
        if not (dest.exists() and dest.stat().st_size > 4096):
            cmd = [
                _ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{start:.2f}", "-i", str(src),
                "-t", f"{seg_seconds:.2f}", "-c", "copy",
                "-avoid_negative_ts", "make_zero", str(dest),
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            except Exception:
                dest.unlink(missing_ok=True)
        if dest.exists() and dest.stat().st_size > 4096:
            made.append(dest)
        start += seg_seconds
        if index >= 8:  # cap clips per source
            break
    return made


def _clip_results(out_dir: Path, query: str) -> list[dict[str, Any]]:
    if not out_dir.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for clip in sorted(out_dir.glob(f"*{_VIDEO_EXT}")):
        if clip.stat().st_size < 4096:
            continue
        width, height, duration = _probe(clip)
        results.append(
            {
                "media_id": clip.stem,
                "source": "youtube",
                "license_lane": "review",  # copyrighted footage — needs human review
                "media_url": "",
                "media_path": str(clip),
                "thumbnail_url": "",
                "title": query,
                "description": query,
                "width": width,
                "height": height,
                "duration": duration,
            }
        )
    return results


_DUR_RE = re.compile(r"Duration: (\d+):(\d+):(\d+\.\d+)")
_RES_RE = re.compile(r", (\d{2,5})x(\d{2,5})")


def _probe(path: Path) -> tuple[int, int, float]:
    try:
        out = subprocess.run(
            [_ffmpeg(), "-hide_banner", "-i", str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60,
        )
    except Exception:
        return 0, 0, 0.0
    stderr = out.stderr or ""
    width = height = 0
    duration = 0.0
    dm = _DUR_RE.search(stderr)
    if dm:
        h, m, s = dm.groups()
        duration = int(h) * 3600 + int(m) * 60 + float(s)
    rm = _RES_RE.search(stderr)
    if rm:
        width, height = int(rm.group(1)), int(rm.group(2))
    return width, height, duration
