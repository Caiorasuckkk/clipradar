import os
import re
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env", override=True)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
_raw_youtube_api_keys = os.getenv("YOUTUBE_API_KEYS", "")
_extra_youtube_keys = [
    key.strip().strip('"').strip("'")
    for key in re.split(r"[,;|\s]+", _raw_youtube_api_keys)
    if key.strip()
]
_numbered_youtube_keys = [
    os.getenv(f"YOUTUBE_API_KEY_{index}", "").strip()
    for index in range(2, 11)
]
_all_youtube_keys = list(
    dict.fromkeys([YOUTUBE_API_KEY] + _extra_youtube_keys + _numbered_youtube_keys)
)
YOUTUBE_API_KEYS_LIST: list[str] = [key for key in _all_youtube_keys if key]
YOUTUBE_API_KEYS = YOUTUBE_API_KEYS_LIST
APP_ENV = os.getenv("APP_ENV", "development")
TOP_TOPICS_TO_PROCESS = int(os.getenv("TOP_TOPICS_TO_PROCESS", "20"))
REPORT_TOP_N = int(os.getenv("REPORT_TOP_N", "20"))
VIDEOS_PER_TOPIC = int(os.getenv("VIDEOS_PER_TOPIC", "5"))
HIGH_ATTENTION_QUERIES_PER_MARKET = int(
    os.getenv("HIGH_ATTENTION_QUERIES_PER_MARKET", "6")
)
ENABLE_HIGH_ATTENTION_SCANNER = (
    os.getenv("ENABLE_HIGH_ATTENTION_SCANNER", "true").lower() == "true"
)
ENABLE_DYNAMIC_QUERY_EXPANSION = (
    os.getenv("ENABLE_DYNAMIC_QUERY_EXPANSION", "true").lower() == "true"
)
DYNAMIC_QUERIES_PER_TOPIC = int(os.getenv("DYNAMIC_QUERIES_PER_TOPIC", "3"))
DYNAMIC_TOPICS_TO_EXPAND = int(os.getenv("DYNAMIC_TOPICS_TO_EXPAND", "10"))
DYNAMIC_QUERY_MIN_SCORE = float(os.getenv("DYNAMIC_QUERY_MIN_SCORE", "5.0"))
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "ClipRadar/0.4.0")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
WHISPER_LANGUAGE_MODE = os.getenv("WHISPER_LANGUAGE_MODE", "auto").strip().lower()
WHISPER_DEFAULT_LANGUAGE = os.getenv("WHISPER_DEFAULT_LANGUAGE", "").strip()
WHISPER_FORCE_PT_MARKET = (
    os.getenv("WHISPER_FORCE_PT_MARKET", "true").lower() == "true"
)
WHISPER_FORCE_PT_CHANNELS = (
    os.getenv("WHISPER_FORCE_PT_CHANNELS", "true").lower() == "true"
)
MAX_VIDEOS_PER_RUN = int(os.getenv("MAX_VIDEOS_PER_RUN", "5"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MIN_CLIP_SECONDS = int(os.getenv("MIN_CLIP_SECONDS", "60"))
MAX_CLIP_SECONDS = int(os.getenv("MAX_CLIP_SECONDS", "150"))
CLIP_END_EXTENSION_SECONDS = int(os.getenv("CLIP_END_EXTENSION_SECONDS", "15"))
TARGET_CLIP_SECONDS = int(os.getenv("TARGET_CLIP_SECONDS", "90"))
SOFT_MAX_CLIP_SECONDS = int(os.getenv("SOFT_MAX_CLIP_SECONDS", "120"))
HARD_MAX_CLIP_SECONDS = int(os.getenv("HARD_MAX_CLIP_SECONDS", "150"))
SHORT_CLIP_SECONDS_MIN = int(os.getenv("SHORT_CLIP_SECONDS_MIN", "45"))
SHORT_CLIP_SECONDS_MAX = int(os.getenv("SHORT_CLIP_SECONDS_MAX", "60"))
FULL_THOUGHT_SECONDS_MIN = int(os.getenv("FULL_THOUGHT_SECONDS_MIN", "75"))
FULL_THOUGHT_SECONDS_MAX = int(os.getenv("FULL_THOUGHT_SECONDS_MAX", "120"))
DIAGNOSTIC_CANDIDATES_TOP_N = int(os.getenv("DIAGNOSTIC_CANDIDATES_TOP_N", "8"))
PODCAST_DISCOVERY_ENABLED = (
    os.getenv("PODCAST_DISCOVERY_ENABLED", "true").lower() == "true"
)
PODCAST_DISCOVERY_MAX_RESULTS = int(os.getenv("PODCAST_DISCOVERY_MAX_RESULTS", "30"))
PODCAST_DISCOVERY_DAYS_BACK = int(os.getenv("PODCAST_DISCOVERY_DAYS_BACK", "14"))
PODCAST_DISCOVERY_MIN_DURATION_SECONDS = int(
    os.getenv("PODCAST_DISCOVERY_MIN_DURATION_SECONDS", "480")
)
PODCAST_DISCOVERY_MAX_PER_CHANNEL = int(
    os.getenv("PODCAST_DISCOVERY_MAX_PER_CHANNEL", "3")
)
PODCAST_DISCOVERY_MARKETS = [
    market.strip().upper()
    for market in os.getenv("PODCAST_DISCOVERY_MARKETS", "BR,GLOBAL").split(",")
    if market.strip()
]

STORAGE_TRENDS_DIR = Path(__file__).resolve().parent / "storage" / "trends"
STORAGE_DOWNLOADS_DIR = Path(__file__).resolve().parent / "storage" / "downloads"
STORAGE_TRANSCRIPTS_DIR = Path(__file__).resolve().parent / "storage" / "transcripts"
STORAGE_CLIPS_DIR = Path(__file__).resolve().parent / "storage" / "clips"
STORAGE_VIDEOS_DIR = Path(__file__).resolve().parent / "storage" / "videos"
STORAGE_REFERENCE_DIR = Path(__file__).resolve().parent / "storage" / "reference"

DEFAULT_BR_FEEDS = [
    "https://g1.globo.com/rss/g1/",
    "https://rss.uol.com.br/feed/noticias.xml",
]

DEFAULT_GLOBAL_FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.cnn.com/rss/edition.rss",
]
