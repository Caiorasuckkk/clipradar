import json
from datetime import datetime, timedelta
from pathlib import Path

from app.config import STORAGE_TRENDS_DIR


class QueryCacheService:
    def __init__(self, cache_path: Path | None = None) -> None:
        self.cache_path = cache_path or (
            STORAGE_TRENDS_DIR.parent / "cache" / "last_queries.json"
        )

    def save_queries(self, queries: list[tuple[str, str]], market: str) -> None:
        if not queries:
            return

        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            existing = self._load_payload()
            saved_queries = [
                query
                for query in existing.get("queries", [])
                if existing.get("markets", {}).get(query) != market.upper()
            ]
            saved_sources = {
                query: source
                for query, source in existing.get("sources", {}).items()
                if existing.get("markets", {}).get(query) != market.upper()
            }
            saved_markets = {
                query: saved_market
                for query, saved_market in existing.get("markets", {}).items()
                if saved_market != market.upper()
            }
            for query, source in queries:
                saved_queries.append(query)
                saved_sources[query] = source
                saved_markets[query] = market.upper()

            payload = {
                "timestamp": datetime.now().isoformat(),
                "queries": saved_queries,
                "sources": saved_sources,
                "markets": saved_markets,
            }
            with self.cache_path.open("w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"[query_cache] Failed to save query cache: {exc}")

    def load_recent(
        self,
        market: str,
        max_age_hours: int = 4,
    ) -> list[tuple[str, str]]:
        try:
            with self.cache_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
            timestamp = datetime.fromisoformat(payload.get("timestamp", ""))
        except Exception:
            return []

        age = datetime.now() - timestamp
        if age > timedelta(hours=max_age_hours):
            return []

        market = market.upper()
        sources = payload.get("sources", {})
        markets = payload.get("markets", {})
        queries: list[tuple[str, str]] = []
        for query in payload.get("queries", []):
            if markets.get(query, market) != market:
                continue
            source = sources.get(query, "cache")
            queries.append((query, f"cache:{source}"))

        if queries:
            age_hours = round(age.total_seconds() / 3600, 1)
            print(
                f"INFO: usando cache de queries de {timestamp.isoformat()} "
                f"({age_hours}h atrás)"
            )
        return queries

    def _load_payload(self) -> dict:
        try:
            with self.cache_path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return {"queries": [], "sources": {}, "markets": {}}
