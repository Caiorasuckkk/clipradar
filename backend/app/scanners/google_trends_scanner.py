from datetime import UTC, datetime

from app.models import TrendSignal


class GoogleTrendsScanner:
    FALLBACK_TRENDS = {
        "BR": [
            "inteligencia artificial no Brasil",
            "economia brasileira",
            "futebol hoje",
            "novelas brasileiras",
            "tecnologia para criadores",
        ],
        "GLOBAL": [
            "artificial intelligence",
            "creator economy",
            "global markets",
            "new movies",
            "viral technology",
        ],
        "US": [
            "artificial intelligence",
            "creator economy",
            "global markets",
            "new movies",
            "viral technology",
        ],
    }

    def __init__(self, market: str, language: str, limit: int = 20) -> None:
        self.market = market.upper()
        self.language = language
        self.limit = limit

    def scan(self) -> list[TrendSignal]:
        keywords, is_mock = self._fetch_trending_searches()
        detected_at = datetime.now(UTC)

        return [
            TrendSignal(
                source="google_trends",
                keyword=keyword,
                title=keyword,
                url=None,
                language=self.language,
                market=self.market,
                raw_score=self._raw_score(index=index, is_mock=is_mock),
                detected_at=detected_at,
                metadata={"rank": index + 1, "is_mock": is_mock},
            )
            for index, keyword in enumerate(keywords[: self.limit])
        ]

    def _fetch_trending_searches(self) -> tuple[list[str], bool]:
        try:
            from pytrends.request import TrendReq

            pytrends = TrendReq(hl=self._hl(), tz=0)
            frame = pytrends.trending_searches(pn=self._pn())
            if frame is None or frame.empty:
                raise ValueError("pytrends returned no trending searches")
            keywords = [
                str(value).strip()
                for value in frame.iloc[:, 0].tolist()
                if str(value).strip()
            ]
            return keywords, False
        except Exception as exc:
            print(f"[google_trends] Falling back to mock trends for {self.market}: {exc}")
            return self.FALLBACK_TRENDS.get(self.market, self.FALLBACK_TRENDS["GLOBAL"]), True

    @staticmethod
    def _raw_score(index: int, is_mock: bool) -> float:
        score = max(10.0, 100.0 - float(index * 4))
        if is_mock:
            score *= 0.35
        return round(score, 2)

    def _pn(self) -> str:
        if self.market == "BR":
            return "brazil"
        return "united_states"

    def _hl(self) -> str:
        return "pt-BR" if self.language.lower().startswith("pt") else "en-US"
