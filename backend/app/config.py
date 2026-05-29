import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
APP_ENV = os.getenv("APP_ENV", "development")

STORAGE_TRENDS_DIR = Path(__file__).resolve().parent / "storage" / "trends"

DEFAULT_BR_FEEDS = [
    "https://g1.globo.com/rss/g1/",
    "https://rss.uol.com.br/feed/noticias.xml",
]

DEFAULT_GLOBAL_FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.cnn.com/rss/edition.rss",
]
