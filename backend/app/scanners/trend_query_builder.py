import json
import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from app.config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    STORAGE_TRENDS_DIR,
)
from app.scanners.high_attention_queries import (
    BR_HIGH_ATTENTION_QUERIES,
    GLOBAL_HIGH_ATTENTION_QUERIES,
)
from app.scanners.keyword_extraction import extract_keyword
from app.services.query_cache_service import QueryCacheService


BR_SUFFIXES = ["podcast", "escândalo", "investigação", "polêmica", "caso", "revelou"]
GLOBAL_SUFFIXES = [
    "podcast",
    "scandal",
    "investigation",
    "files",
    "exposed",
    "lawsuit",
]

STOPWORDS_PT = {
    "o",
    "a",
    "os",
    "as",
    "de",
    "da",
    "do",
    "das",
    "dos",
    "em",
    "com",
    "que",
    "para",
    "por",
    "um",
    "uma",
    "uns",
    "umas",
    "e",
    "é",
    "se",
    "não",
    "na",
    "no",
    "nas",
    "nos",
    "ao",
    "aos",
    "pelo",
    "pela",
    "pelos",
    "pelas",
    "mais",
    "mas",
    "ou",
    "já",
    "como",
    "seu",
    "sua",
    "seus",
    "suas",
    "este",
    "esta",
    "isso",
}
STOPWORDS_EN = {
    "the",
    "a",
    "an",
    "of",
    "in",
    "on",
    "at",
    "to",
    "for",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "and",
    "or",
    "but",
    "with",
    "this",
    "that",
    "its",
    "it",
    "he",
    "she",
    "they",
    "we",
    "you",
}
STOPWORDS = STOPWORDS_PT | STOPWORDS_EN
REDDIT_BR_SUBREDDITS = ["brasil", "brasilivre", "choquei", "fofoca"]
YOUTUBE_TITLE_PATTERNS = [
    r'"title":\{"runs":\[\{"text":"([^"]{10,100})"\}',
    r'"title":\{"simpleText":"([^"]{10,100})"',
    r'"videoTitle":"([^"]{10,100})"',
    r'"headline":\{"simpleText":"([^"]{10,100})"',
    r'aria-label="([^"]{15,120})"',
]
QUERY_EVENTS: list[dict[str, str]] = []
SOURCE_STATUS: list[dict[str, str | bool]] = []
YT_TRENDING_DEBUG_PATH = STORAGE_TRENDS_DIR.parent / "cache" / "yt_trending_debug.html"

BR_CONTEXT_WORDS = {
    "de",
    "da",
    "do",
    "das",
    "dos",
    "em",
    "com",
    "que",
    "para",
    "por",
    "são",
    "é",
    "não",
    "na",
    "no",
    "caso",
    "processo",
    "escândalo",
    "polícia",
    "governo",
    "brasil",
    "federal",
    "ministério",
    "deputado",
    "senador",
    "presidente",
}
BR_INTEREST_TERMS = {
    "banco master",
    "stf",
    "senado",
    "câmara",
    "camara",
    "lula",
    "bolsonaro",
    "flamengo",
    "corinthians",
    "globo",
    "cazétv",
    "cazetv",
    "flow",
    "podpah",
    "inteligência ltda",
    "inteligencia ltda",
}
GLOBAL_ALLOWED_TERMS = {
    "trump",
    "biden",
    "musk",
    "epstein",
    "diddy",
    "assange",
    "snowden",
    "bezos",
    "gates",
    "obama",
    "ronaldo",
    "champions league",
    "call of duty",
}
BR_DYNAMIC_SEED_QUERIES = [
    "podcast polêmica hoje",
    "corte podcast viral",
    "política hoje polêmica",
    "escândalo financeiro Brasil",
    "investigação famoso",
    "influenciador polêmica",
    "denúncia hoje",
    "fraude banco",
    "operação polícia política",
    "cortes podcast revelação",
]


def reset_query_debug() -> None:
    QUERY_EVENTS.clear()
    SOURCE_STATUS.clear()


def get_query_events() -> list[dict[str, str]]:
    return list(QUERY_EVENTS)


def get_source_status() -> list[dict[str, str | bool]]:
    return list(SOURCE_STATUS)


class TrendQueryBuilder:
    def __init__(self, market: str = "BR", max_queries: int = 6) -> None:
        self.market = market.upper()
        self.max_queries = max_queries
        self.cache_service = QueryCacheService()

    def build_queries(self) -> list[str]:
        queries = self._dynamic_queries()
        deduped = self._dedupe_pairs(queries)
        if deduped:
            self.cache_service.save_queries(deduped, self.market)
            return [query for query, _ in deduped[: self.max_queries]]

        cached = self._dedupe_pairs(self.cache_service.load_recent(self.market))
        if cached:
            return [query for query, _ in cached[: self.max_queries]]

        print("WARNING: usando queries estáticas — fontes dinâmicas indisponíveis")
        fallback = (
            BR_HIGH_ATTENTION_QUERIES
            if self.market == "BR"
            else GLOBAL_HIGH_ATTENTION_QUERIES
        )
        _record_status("Fallback estático", True, f"{self.market} — fonte estática usada")
        static_pairs = self._dedupe_pairs([(query, "fallback") for query in fallback])
        return [query for query, _ in static_pairs[: self.max_queries]]

    def _dynamic_queries(self) -> list[tuple[str, str]]:
        queries: list[tuple[str, str]] = []
        _record_status(
            f"pytrends {self.market}",
            False,
            "endpoint 404 removido em 2024; ignorado",
        )
        queries.extend(self._youtube_trending_queries())

        if len(queries) < self.max_queries:
            queries.extend(self._google_trends_rss_queries())

        if self.market == "BR" and len(queries) < self.max_queries:
            queries.extend(self._reddit_br_queries())

        return queries

    def _youtube_trending_queries(self) -> list[tuple[str, str]]:
        label = f"YouTube Trending {self.market}"
        url = (
            "https://www.youtube.com/feed/trending?bp=4gINGgt5dGRfY2hhcnRz&gl=BR&hl=pt"
            if self.market == "BR"
            else "https://www.youtube.com/feed/trending?bp=4gINGgt5dGRfY2hhcnRz&gl=US&hl=en"
        )
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9" if self.market == "BR" else "en-US,en;q=0.9",
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            raw_titles = self._extract_youtube_titles(response.text)
            titles = self._unique_titles(raw_titles)
            if len(titles) < 3:
                raise ValueError(f"menos de 3 títulos encontrados ({len(titles)})")

            source = "yt-trending"
            queries = self._queries_from_terms(
                [self._extract_topic_from_title(title) for title in titles[:15]],
                source,
            )
            _record_status(label, True, f"{len(queries[: self.max_queries])} queries geradas")
            return queries
        except Exception as exc:
            detail = f"falhou: {exc}"
            if YT_TRENDING_DEBUG_PATH.exists():
                detail += f"; debug_saved={YT_TRENDING_DEBUG_PATH}"
            _record_status(label, False, detail)
            print(f"[trend_query_builder] {label} unavailable: {exc}")
            return []

    def _google_trends_rss_queries(self) -> list[tuple[str, str]]:
        label = f"Google Trends RSS {self.market}"
        geo = "BR" if self.market == "BR" else "US"
        hl = "pt-BR" if self.market == "BR" else "en-US"
        url = f"https://trends.google.com/trending/rss?geo={geo}&hl={hl}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            titles = [
                item.findtext("title", default="").strip()
                for item in root.findall(".//item")
            ]
            terms = [title for title in titles if title][:12]
            if not terms:
                raise ValueError("RSS sem itens")
            filtered_count = 0
            auxiliary_count = 0
            if self.market == "BR":
                strong_terms = []
                auxiliary_terms = []
                for term in terms:
                    relevance = _br_relevance_score(term)
                    if relevance >= 0.45:
                        strong_terms.append(term)
                    elif relevance >= 0.25:
                        auxiliary_terms.append(term)
                filtered_count = len(terms) - len(strong_terms) - len(auxiliary_terms)
                auxiliary_count = len(auxiliary_terms)
                terms = strong_terms + auxiliary_terms
                if len(strong_terms) < 3:
                    print(
                        "[trend_query_builder] BR Trends com poucos termos fortes; "
                        "complementando com seeds high-attention genéricas."
                    )
                    terms.extend(BR_DYNAMIC_SEED_QUERIES)

            queries = self._queries_from_trends_terms(terms, "trends-rss")
            detail = f"{len(queries[: self.max_queries])} queries geradas"
            if self.market == "BR":
                detail += f"; filtered_count={filtered_count}; auxiliary_count={auxiliary_count}"
            _record_status(label, True, detail)
            return queries
        except Exception as exc:
            _record_status(label, False, f"falhou: {exc}")
            print(f"[trend_query_builder] {label} unavailable: {exc}")
            return []

    def _reddit_br_queries(self) -> list[tuple[str, str]]:
        label = "Reddit BR"
        if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
            _record_status(label, False, "credenciais ausentes")
            print("[trend_query_builder] Reddit credentials missing; skipping Reddit BR.")
            return []

        try:
            import praw

            reddit = praw.Reddit(
                client_id=REDDIT_CLIENT_ID,
                client_secret=REDDIT_CLIENT_SECRET,
                user_agent=REDDIT_USER_AGENT,
            )
            posts = []
            for subreddit_name in REDDIT_BR_SUBREDDITS:
                for submission in reddit.subreddit(subreddit_name).hot(limit=8):
                    posts.append((getattr(submission, "score", 0), submission.title))

            queries = []
            for _, title in sorted(posts, reverse=True)[:5]:
                keyword = extract_keyword(title, max_words=4)
                if keyword:
                    queries.append((keyword, "reddit-br"))
            _record_status(label, True, f"{len(queries)} queries geradas")
            return queries
        except Exception as exc:
            _record_status(label, False, f"falhou: {exc}")
            print(f"[trend_query_builder] Reddit BR unavailable: {exc}")
            return []

    def _queries_from_terms(self, terms: list[str], source: str) -> list[tuple[str, str]]:
        suffixes = BR_SUFFIXES if self.market == "BR" else GLOBAL_SUFFIXES
        queries: list[tuple[str, str]] = []
        for term in terms:
            topic = " ".join(term.split()).strip()
            if not topic:
                continue
            for suffix in suffixes:
                queries.append((f"{topic} {suffix}", source))
                if len(queries) >= self.max_queries:
                    return queries
        return queries

    def _queries_from_trends_terms(self, terms: list[str], source: str) -> list[tuple[str, str]]:
        suffixes = BR_SUFFIXES if self.market == "BR" else GLOBAL_SUFFIXES
        candidates: list[tuple[str, str]] = []
        for term in terms:
            topic = " ".join(term.split()).strip()
            if not topic:
                continue
            for suffix in suffixes[:2]:
                candidates.append((f"{topic} {suffix}", source))
        return sorted(candidates, key=lambda item: len(item[0]), reverse=True)[: self.max_queries]

    @staticmethod
    def _extract_youtube_titles(html: str) -> list[str]:
        decoded_html = html_module_unescape(html)
        for index, pattern in enumerate(YOUTUBE_TITLE_PATTERNS, start=1):
            try:
                matches = re.findall(pattern, decoded_html)
            except Exception as exc:
                print(f"[trend_query_builder] YouTube Trending pattern {index} failed: {exc}")
                continue
            valid_matches = _valid_youtube_titles(matches)
            if len(valid_matches) >= 3:
                print(
                    f"[trend_query_builder] YouTube Trending: padrão {index} "
                    f"funcionou, {len(valid_matches)} títulos"
                )
                return valid_matches[:15]
        _save_youtube_debug_html(decoded_html)
        print(
            f"[trend_query_builder] YouTube Trending HTML: {len(decoded_html)} bytes, "
            f"0 títulos extraídos; debug salvo em {YT_TRENDING_DEBUG_PATH}"
        )
        return []

    def _extract_topic_from_title(self, title: str) -> str:
        """Extrai 2-4 palavras relevantes de um título de vídeo."""
        words = re.findall(r"\b[A-Za-zÀ-ÿ]{3,}\b", title)
        filtered = [word for word in words if word.lower() not in STOPWORDS]
        capitalized = [word for word in filtered if word[0].isupper()]
        result = capitalized[:2] + [
            word for word in filtered if word not in capitalized
        ][:2]
        return " ".join(result[:4])

    def _dedupe_pairs(self, queries: list[tuple[str, str]]) -> list[tuple[str, str]]:
        seen: set[str] = set()
        result: list[tuple[str, str]] = []
        for query, source in queries:
            cleaned = " ".join(query.split()).strip()
            normalized = cleaned.lower()
            if normalized in seen or not self._valid_query(cleaned):
                continue
            seen.add(normalized)
            result.append((cleaned, source))
            QUERY_EVENTS.append(
                {"source": source, "market": self.market, "query": cleaned}
            )
            print(f"[trend_query_builder] query source={source} market={self.market}: {cleaned}")
            if len(result) >= self.max_queries:
                break
        return result

    def _unique_titles(self, raw_titles: list[str]) -> list[str]:
        seen: set[str] = set()
        titles: list[str] = []
        for raw_title in raw_titles:
            title = _decode_js_string(raw_title)
            normalized = title.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            titles.append(title)
        return titles

    @staticmethod
    def _valid_query(query: str) -> bool:
        words = [word.lower() for word in query.split() if word.strip()]
        if len(words) < 2:
            return False
        return any(word not in STOPWORDS for word in words)


def _record_status(name: str, ok: bool, detail: str) -> None:
    SOURCE_STATUS.append({"name": name, "ok": ok, "detail": detail})


def _decode_js_string(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except Exception:
        return value


def _br_relevance_score(term: str) -> float:
    """
    Retorna score de 0 a 1 indicando se o termo parece relevante para o Brasil.
    Não deve eliminar automaticamente nomes globais importantes.
    """
    text = term.lower()
    words = re.findall(r"\b[\wÀ-ÿ]+\b", text)
    score = 0.0
    if any(word in BR_CONTEXT_WORDS for word in words):
        score += 0.35
    if re.search(r"[áàâãéêíóôõúç]", text):
        score += 0.25
    if any(term in text for term in BR_INTEREST_TERMS):
        score += 0.55
    if any(term in text for term in GLOBAL_ALLOWED_TERMS):
        score += 0.45
    if len(words) <= 3 and text.isascii() and score < 0.45:
        score -= 0.25
    if _looks_like_random_us_name(words, text) and score < 0.45:
        score -= 0.25
    return max(0.0, min(1.0, score))


def _looks_like_random_us_name(words: list[str], text: str) -> bool:
    if not text.isascii() or len(words) not in {2, 3}:
        return False
    context_terms = BR_INTEREST_TERMS | GLOBAL_ALLOWED_TERMS | {
        "podcast",
        "scandal",
        "investigation",
        "lawsuit",
        "files",
        "football",
        "soccer",
    }
    return not any(term in text for term in context_terms)


def html_module_unescape(value: str) -> str:
    return html.unescape(value)


def _valid_youtube_titles(matches: list[str]) -> list[str]:
    seen: set[str] = set()
    titles: list[str] = []
    for raw_title in matches:
        title = _decode_js_string(raw_title)
        title = html_module_unescape(title)
        title = re.sub(r"\s+", " ", title).strip()
        if not 10 <= len(title) <= 120:
            continue
        lowered = title.lower()
        if any(term in lowered for term in ["views", "visualizações", "aria-label", "http"]):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        titles.append(title)
    return titles


def _save_youtube_debug_html(decoded_html: str) -> None:
    try:
        YT_TRENDING_DEBUG_PATH.parent.mkdir(parents=True, exist_ok=True)
        YT_TRENDING_DEBUG_PATH.write_text(decoded_html[:5000], encoding="utf-8")
    except Exception as exc:
        print(f"[trend_query_builder] Failed to save YouTube debug HTML: {exc}")
