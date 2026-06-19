import os
import re
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
BACKEND_ENV_PATH = BACKEND_DIR / ".env"
if BACKEND_ENV_PATH.exists():
    load_dotenv(BACKEND_ENV_PATH, override=True)
else:
    load_dotenv(override=True)

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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
GENERATION_ENGINE = os.getenv("GENERATION_ENGINE", "local").strip().lower()
GENERATION_AI_PROVIDER = os.getenv("GENERATION_AI_PROVIDER", "none").strip().lower()
# OpenAI provider (alternative to Gemini). Smart split: strong model on
# research/script/judge, cheap model on trivial steps. Web search replaces
# Gemini grounding for current facts. All model ids are env-overridable so a
# wrong default can be fixed without code changes.
GENERATION_OPENAI_RESEARCH_MODEL = os.getenv("GENERATION_OPENAI_RESEARCH_MODEL", "gpt-5.4").strip()
GENERATION_OPENAI_SCRIPT_MODEL = os.getenv("GENERATION_OPENAI_SCRIPT_MODEL", "gpt-5.4").strip()
GENERATION_OPENAI_CHEAP_MODEL = os.getenv("GENERATION_OPENAI_CHEAP_MODEL", "gpt-5.4-mini").strip()
# Judge is evaluative (not writing) — defaults to the cheap model to save tokens.
GENERATION_OPENAI_JUDGE_MODEL = os.getenv(
    "GENERATION_OPENAI_JUDGE_MODEL", GENERATION_OPENAI_CHEAP_MODEL
).strip()
GENERATION_OPENAI_USE_WEB_SEARCH = (
    os.getenv("GENERATION_OPENAI_USE_WEB_SEARCH", "true").lower() == "true"
)
# AI image generation as a LAST-RESORT visual (only when stock + Wikimedia have
# nothing). Priced per image, so use the cheap model at low quality and cap how
# many per video to control cost. Covers gaps stock can't: modern people,
# current athletes, anime (style), etc.
GENERATION_ENABLE_AI_IMAGE_FALLBACK = (
    os.getenv("GENERATION_ENABLE_AI_IMAGE_FALLBACK", "true").lower() == "true"
)
GENERATION_OPENAI_IMAGE_MODEL = os.getenv("GENERATION_OPENAI_IMAGE_MODEL", "gpt-image-1-mini").strip()
GENERATION_IMAGE_QUALITY = os.getenv("GENERATION_IMAGE_QUALITY", "low").strip().lower()
GENERATION_IMAGE_SIZE = os.getenv("GENERATION_IMAGE_SIZE", "1024x1536").strip()
# Runware (Flux) — gerador de imagem PRINCIPAL (mais barato que o OpenAI). OpenAI
# vira só último recurso. Modelo padrão: FLUX.1 Schnell (runware:100@1).
RUNWARE_API_KEY = os.getenv("RUNWARE_API_KEY", "").strip()
GENERATION_RUNWARE_ENABLED = (
    os.getenv("GENERATION_RUNWARE_ENABLED", "true").lower() == "true"
)
GENERATION_RUNWARE_MODEL = os.getenv("GENERATION_RUNWARE_MODEL", "runware:100@1").strip()
GENERATION_MAX_AI_IMAGES_PER_VIDEO = int(os.getenv("GENERATION_MAX_AI_IMAGES_PER_VIDEO", "24"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GENERATION_REQUIRE_EXTERNAL_AI = (
    os.getenv("GENERATION_REQUIRE_EXTERNAL_AI", "false").lower() == "true"
)
GENERATION_USE_WEB_GROUNDING = (
    os.getenv("GENERATION_USE_WEB_GROUNDING", "false").lower() == "true"
)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()
GEMINI_RESEARCH_MODEL = os.getenv("GEMINI_RESEARCH_MODEL", GEMINI_MODEL).strip()
GEMINI_SCRIPT_MODEL = os.getenv("GEMINI_SCRIPT_MODEL", GEMINI_MODEL).strip()
# Judge defaults to the cheap/lite model (evaluation doesn't need the strong one).
GEMINI_JUDGE_MODEL = os.getenv("GEMINI_JUDGE_MODEL", GEMINI_MODEL).strip()
GENERATION_GEMINI_MODEL = os.getenv("GENERATION_GEMINI_MODEL", GEMINI_MODEL).strip()
GENERATION_MAX_RESEARCH_CALLS_PER_PROJECT = int(
    os.getenv("GENERATION_MAX_RESEARCH_CALLS_PER_PROJECT", "3")
)
GENERATION_MAX_SCRIPT_CALLS_PER_PROJECT = int(
    os.getenv("GENERATION_MAX_SCRIPT_CALLS_PER_PROJECT", "3")
)
GENERATION_RESEARCH_CACHE_TTL_DAYS = int(
    os.getenv("GENERATION_RESEARCH_CACHE_TTL_DAYS", "7")
)
# LLM-as-judge for script quality (Fase 2). One cheap flash call scores the
# script; if it is weak the script is rewritten with the critique. The regex
# scorer becomes advisory-only when the judge runs.
GENERATION_ENABLE_LLM_JUDGE = (
    os.getenv("GENERATION_ENABLE_LLM_JUDGE", "true").lower() == "true"
)
GENERATION_JUDGE_REWRITE_THRESHOLD = float(
    os.getenv("GENERATION_JUDGE_REWRITE_THRESHOLD", "7.5")
)
GENERATION_MAX_SCRIPT_REWRITES = int(
    os.getenv("GENERATION_MAX_SCRIPT_REWRITES", "3")
)
# Hard quality gate: the auto pipeline refuses to build a video from a script
# scored below this by the judge (only enforced when the judge actually ran).
GENERATION_MIN_ACCEPT_SCORE = float(os.getenv("GENERATION_MIN_ACCEPT_SCORE", "7.5"))
# LLM-driven visual queries (Fase: visual matching). One batched flash call turns
# each script beat into generic English stock-search queries that visually match
# the narration. Falls back to the hardcoded dictionary when disabled/unavailable.
GENERATION_ENABLE_LLM_VISUAL_QUERIES = (
    os.getenv("GENERATION_ENABLE_LLM_VISUAL_QUERIES", "true").lower() == "true"
)
GENERATION_MAX_VISUAL_QUERIES_PER_ITEM = int(
    os.getenv("GENERATION_MAX_VISUAL_QUERIES_PER_ITEM", "3")
)
# Visual density: aim for a new image roughly every N seconds (more cuts = more
# dynamic). A 60s video at 4s/visual gets ~15 images. Capped by MAX_VISUALS.
GENERATION_SECONDS_PER_VISUAL = float(os.getenv("GENERATION_SECONDS_PER_VISUAL", "4"))
GENERATION_MAX_VISUALS = int(os.getenv("GENERATION_MAX_VISUALS", "24"))
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "").strip()
# Premium TTS providers (more realistic narration than edge-tts).
# OpenAI TTS uses the existing OPENAI_API_KEY (enable the model in Allowed models).
GENERATION_OPENAI_TTS_MODEL = os.getenv("GENERATION_OPENAI_TTS_MODEL", "tts-1-hd").strip()
# Caption sync: OpenAI TTS returns no word timings, so we transcribe the generated
# audio with Whisper (word-level timestamps) to lock subtitles to the real speech.
# ~US$0.006/min of audio. whisper-1 is the model that supports word granularities.
GENERATION_ALIGN_CAPTIONS = (
    os.getenv("GENERATION_ALIGN_CAPTIONS", "true").lower() == "true"
)
GENERATION_OPENAI_TRANSCRIBE_MODEL = os.getenv(
    "GENERATION_OPENAI_TRANSCRIBE_MODEL", "whisper-1"
).strip()
# Local XTTS voice (cloned "Marco" voice on the user's GPU). The backend shells out
# to the isolated tts_test venv so heavy TTS deps never touch the backend env.
# Selected by a voice named "xtts:<id>" (or "local:<id>").
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATION_XTTS_ENABLED = (
    os.getenv("GENERATION_XTTS_ENABLED", "true").lower() == "true"
)
GENERATION_XTTS_PYTHON = os.getenv(
    "GENERATION_XTTS_PYTHON", str(_PROJECT_ROOT / "tts_test" / ".venv" / "Scripts" / "python.exe")
).strip()
GENERATION_XTTS_SCRIPT = os.getenv(
    "GENERATION_XTTS_SCRIPT", str(_PROJECT_ROOT / "tts_test" / "xtts_synth.py")
).strip()
GENERATION_XTTS_REF = os.getenv(
    "GENERATION_XTTS_REF",
    str(Path(__file__).resolve().parent / "storage" / "generation" / "persona" / "voz_ref_clean.wav"),
).strip()
GENERATION_XTTS_SPEED = float(os.getenv("GENERATION_XTTS_SPEED", "1.15"))
GENERATION_XTTS_TEMPERATURE = float(os.getenv("GENERATION_XTTS_TEMPERATURE", "0.75"))
# Voz padrão para vídeos NÃO-português (ex.: canal em inglês). A voz clonada é
# treinada em pt; pra inglês nativo usamos uma voz pronta (OpenAI TTS). Cada estúdio
# pode sobrescrever via persona["voice_en"].
GENERATION_ENGLISH_VOICE = os.getenv("GENERATION_ENGLISH_VOICE", "openai:onyx").strip()
# Clean the generated voice (denoise background hiss/hum + normalize) so it sounds
# less "robotic". Applied during the WAV->MP3 step.
GENERATION_XTTS_CLEAN_AUDIO = (
    os.getenv("GENERATION_XTTS_CLEAN_AUDIO", "true").lower() == "true"
)
# Filtro ffmpeg de limpeza: denoise leve + realce de presença (treble) pra não
# abafar. Ajustável via env sem mexer no código.
GENERATION_XTTS_CLEAN_FILTER = os.getenv(
    "GENERATION_XTTS_CLEAN_FILTER",
    "highpass=f=70,afftdn=nr=6:nf=-25,treble=g=4:f=3500,loudnorm=I=-16:TP=-1.5:LRA=11",
).strip()
# ElevenLabs (most human). Add the key to enable; multilingual model handles pt-BR.
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
GENERATION_ELEVENLABS_MODEL = os.getenv("GENERATION_ELEVENLABS_MODEL", "eleven_multilingual_v2").strip()
GENERATION_VISUAL_PROVIDER = os.getenv("GENERATION_VISUAL_PROVIDER", "local").strip().lower()
GENERATION_ENABLE_STOCK_SEARCH = (
    os.getenv("GENERATION_ENABLE_STOCK_SEARCH", "false").lower() == "true"
)
GENERATION_MAX_STOCK_RESULTS = int(os.getenv("GENERATION_MAX_STOCK_RESULTS", "8"))
# Wikimedia Commons as an extra media source (free, no API key) — strong for
# history, real people, places and events that stock libraries lack.
GENERATION_ENABLE_WIKIMEDIA = (
    os.getenv("GENERATION_ENABLE_WIKIMEDIA", "true").lower() == "true"
)
GENERATION_WIKIMEDIA_MAX_RESULTS = int(os.getenv("GENERATION_WIKIMEDIA_MAX_RESULTS", "6"))
# Extra media sources. Pixabay = more generic stock (photo+video, free key, no
# attribution). Openverse = millions of CC images (no key, some need credit).
# Met Museum = public-domain art/artifacts (no key) — great for history.
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "").strip()
GENERATION_ENABLE_PIXABAY = (
    os.getenv("GENERATION_ENABLE_PIXABAY", "true").lower() == "true"
)
GENERATION_ENABLE_OPENVERSE = (
    os.getenv("GENERATION_ENABLE_OPENVERSE", "true").lower() == "true"
)
GENERATION_ENABLE_MET = (
    os.getenv("GENERATION_ENABLE_MET", "true").lower() == "true"
)
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
STORAGE_EXPORTS_DIR = Path(__file__).resolve().parent / "storage" / "exports"
STORAGE_VERTICAL_EXPORTS_DIR = Path(__file__).resolve().parent / "storage" / "vertical_exports"
STORAGE_FINAL_EXPORTS_DIR = Path(__file__).resolve().parent / "storage" / "final_exports"
STORAGE_SUBTITLED_EXPORTS_DIR = Path(__file__).resolve().parent / "storage" / "subtitled_exports"
STORAGE_SUBTITLES_DIR = Path(__file__).resolve().parent / "storage" / "subtitles"
STORAGE_CLIP_TRANSCRIPTS_DIR = Path(__file__).resolve().parent / "storage" / "clip_transcripts"
STORAGE_VIDEOS_DIR = Path(__file__).resolve().parent / "storage" / "videos"
STORAGE_REVIEWS_DIR = Path(__file__).resolve().parent / "storage" / "reviews"
STORAGE_FINAL_REVIEWS_DIR = Path(__file__).resolve().parent / "storage" / "final_reviews"
STORAGE_POSTING_PACKAGE_DIR = Path(__file__).resolve().parent / "storage" / "posting_package"
STORAGE_POST_METADATA_DIR = Path(__file__).resolve().parent / "storage" / "post_metadata"
STORAGE_CANDIDATE_QUEUE_DIR = Path(__file__).resolve().parent / "storage" / "candidate_queue"
STORAGE_CANDIDATE_PREVIEWS_DIR = Path(__file__).resolve().parent / "storage" / "candidate_previews"
STORAGE_CANDIDATE_REVIEWS_DIR = Path(__file__).resolve().parent / "storage" / "candidate_reviews"
STORAGE_JOB_RUNS_DIR = Path(__file__).resolve().parent / "storage" / "job_runs"
STORAGE_GENERATION_STATE_DIR = Path(__file__).resolve().parent / "storage" / "generation_state"
STORAGE_GENERATION_DIR = Path(__file__).resolve().parent / "storage" / "generation"
STORAGE_GENERATION_RENDERS_DIR = Path(__file__).resolve().parent / "storage" / "generation" / "renders"
STORAGE_GENERATION_ASSETS_DIR = Path(__file__).resolve().parent / "storage" / "generation" / "assets"
STORAGE_GENERATION_AUDIO_DIR = Path(__file__).resolve().parent / "storage" / "generation" / "audio"
# Drop royalty-free .mp3/.m4a/.wav tracks here to enable background music.
STORAGE_GENERATION_MUSIC_DIR = Path(__file__).resolve().parent / "storage" / "generation" / "music"
STORAGE_REFERENCE_DIR = Path(__file__).resolve().parent / "storage" / "reference"

# SQLite-backed job queue (Bloco A foundation). State/index lives in SQLite,
# heavy media stays on disk under storage/generation/*.
STORAGE_DB_PATH = Path(__file__).resolve().parent / "storage" / "darkflow.db"

# Generation render pipeline (Bloco B)
GENERATION_RENDER_WIDTH = int(os.getenv("GENERATION_RENDER_WIDTH", "1080"))
GENERATION_RENDER_HEIGHT = int(os.getenv("GENERATION_RENDER_HEIGHT", "1920"))
GENERATION_RENDER_FPS = int(os.getenv("GENERATION_RENDER_FPS", "30"))
GENERATION_RENDER_MAX_SECONDS = int(os.getenv("GENERATION_RENDER_MAX_SECONDS", "90"))
GENERATION_RENDER_TIMEOUT_SECONDS = int(os.getenv("GENERATION_RENDER_TIMEOUT_SECONDS", "1200"))
GENERATION_JOB_MAX_ATTEMPTS = int(os.getenv("GENERATION_JOB_MAX_ATTEMPTS", "2"))

# Render quality (0.5.53): narration polishing, captions, smarter visual search
GENERATION_DEFAULT_NARRATION_STYLE = os.getenv(
    "GENERATION_DEFAULT_NARRATION_STYLE", "conversational_story"
).strip()
GENERATION_DEFAULT_VOICE_RATE = os.getenv("GENERATION_DEFAULT_VOICE_RATE", "-6%").strip()
GENERATION_CAPTION_MIN_WORDS = int(os.getenv("GENERATION_CAPTION_MIN_WORDS", "2"))
GENERATION_CAPTION_MAX_WORDS = int(os.getenv("GENERATION_CAPTION_MAX_WORDS", "4"))
GENERATION_RENDER_DEBUG = os.getenv("GENERATION_RENDER_DEBUG", "true").lower() == "true"

# Viral caption styling (burned-in ASS subtitles).
GENERATION_CAPTION_FONT = os.getenv("GENERATION_CAPTION_FONT", "Arial").strip()
GENERATION_CAPTION_FONTSIZE = int(os.getenv("GENERATION_CAPTION_FONTSIZE", "92"))
GENERATION_CAPTION_UPPERCASE = (
    os.getenv("GENERATION_CAPTION_UPPERCASE", "true").lower() == "true"
)
# Animated word-by-word captions: highlight the spoken word (viral TikTok style).
# Needs per-word timings (Whisper). Color is ASS format &HBBGGRR& — default cyan
# (0x38D9FF -> &HFFD938&).
GENERATION_CAPTION_HIGHLIGHT = (
    os.getenv("GENERATION_CAPTION_HIGHLIGHT", "true").lower() == "true"
)
GENERATION_CAPTION_HIGHLIGHT_COLOR = os.getenv(
    "GENERATION_CAPTION_HIGHLIGHT_COLOR", "&HFFD938&"
).strip()
# Break a caption block when there's a real pause in the speech (gap between words
# >= this many seconds) — keeps phrases together instead of cutting mid-expression.
GENERATION_CAPTION_PAUSE_GAP = float(os.getenv("GENERATION_CAPTION_PAUSE_GAP", "0.28"))

# Background music: mixed low under the narration. Drop tracks in the music dir.
GENERATION_ENABLE_BG_MUSIC = (
    os.getenv("GENERATION_ENABLE_BG_MUSIC", "true").lower() == "true"
)
GENERATION_BG_MUSIC_VOLUME = float(os.getenv("GENERATION_BG_MUSIC_VOLUME", "0.10"))
# Loudness do áudio final do vídeo (LUFS). -14 é o padrão "alto" de TikTok/YouTube
# — garante que o vídeo não saia baixo no feed.
GENERATION_AUDIO_LOUDNORM_I = os.getenv("GENERATION_AUDIO_LOUDNORM_I", "-14").strip()

# Ken Burns: slow zoom on still images so the video looks edited (not a slideshow).
# Videos/b-roll already move and are left untouched. Zoom amount is the fraction of
# extra zoom across a clip (0.12 = up to +12%). Direction alternates per scene.
GENERATION_ENABLE_KEN_BURNS = (
    os.getenv("GENERATION_ENABLE_KEN_BURNS", "true").lower() == "true"
)
GENERATION_KENBURNS_ZOOM = float(os.getenv("GENERATION_KENBURNS_ZOOM", "0.12"))

# Persona branding: drop a square photo at storage/generation/persona/avatar.png.
# INTRO = a quick full-frame flash of the persona at the very start (over the hook
# audio, so it never adds dead air). WATERMARK = a small circular face "bug" in the
# corner for the whole video. Both make the channel look authored/recognizable.
GENERATION_PERSONA_INTRO = (
    os.getenv("GENERATION_PERSONA_INTRO", "false").lower() == "true"
)
GENERATION_PERSONA_INTRO_SECONDS = float(os.getenv("GENERATION_PERSONA_INTRO_SECONDS", "1.2"))
GENERATION_PERSONA_WATERMARK = (
    os.getenv("GENERATION_PERSONA_WATERMARK", "false").lower() == "true"
)
GENERATION_PERSONA_WATERMARK_SIZE = int(os.getenv("GENERATION_PERSONA_WATERMARK_SIZE", "140"))

DEFAULT_BR_FEEDS = [
    "https://g1.globo.com/rss/g1/",
    "https://rss.uol.com.br/feed/noticias.xml",
]

DEFAULT_GLOBAL_FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.cnn.com/rss/edition.rss",
]
