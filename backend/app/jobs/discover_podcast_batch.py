from __future__ import annotations

import json
import re
import sys
import argparse
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from math import log10
from typing import Any

import isodate
from googleapiclient.discovery import build

from app import config
from app.models import SourceVideo
from app.scanners import youtube_errors
from app.scanners.youtube_errors import (
    KeyRotationManager,
    is_quota_error,
    mark_quota_exhausted,
    sanitize_youtube_error,
)
from app.services.processing_priority_service import ProcessingPriorityService
from app.services.video_history_service import VideoHistoryService


BR_QUERIES = [
    "Flow Podcast entrevista",
    "Podpah entrevista",
    "Podpah Rango Brabo entrevista",
    "Rango Brabo Podpah famoso",
    "Rango Brabo jogador",
    "Quebrada FC Podpah",
    "Quebrada FC jogador entrevista",
    "Podpah futebol bastidores",
    "Podpah histórias famoso",
    "Podpah visita entrevista",
    "Podpah de Verão entrevista",
    "Inteligência Ltda entrevista",
    "Ticaracaticast entrevista",
    "Venus Podcast entrevista",
    "Papo de Elite podcast",
    "À Deriva Podcast entrevista",
    "PrimoCast entrevista",
    "Jota Jota Podcast entrevista",
    "The Noite entrevista",
    "Programa do João entrevista",
    "RedCast podcast entrevista",
    "RedCast convidado famoso",
    "Ciência Sem Fim podcast entrevista",
    "Achismos TV entrevista",
    "Achismos Podcast",
    "Achismos TV ciência",
    "Achismos TV comportamento",
    "Achismos TV polêmica",
    "Achismos TV cortes",
    "Achismos TV sociedade",
    "Achismos TV convidado",
    "Os Sócios Podcast entrevista",
    "Cara a Tapa entrevista",
    "Nômade Raiz viagem história",
    "Nômade Raiz relato viagem",
    "Nômade Raiz histórias pelo mundo",
    "Nômade Raiz perrengue viagem",
    "Nômade Raiz cultura",
    "Nômade Raiz países perigosos",
    "Nômade Raiz curiosidades",
    "Nômade Raiz entrevista",
    "Cortes podcast convidado famoso",
    "Podcast convidado famoso polêmica",
    "Podcast história engraçada famoso",
    "Podcast bastidores famoso",
    "Entrevista famoso podcast Brasil",
    "Futebol podcast polêmica",
    "Jogador entrevista podcast",
    "Ex jogador entrevista podcast",
]

BR_TREND_QUERIES = [
    "Neymar polêmica podcast",
    "Neymar bastidores entrevista",
    "Neymar Copa do Mundo podcast",
    "Copa do Mundo bastidores podcast",
    "Copa do Mundo polêmica futebol podcast",
    "seleção brasileira bastidores podcast",
    "futebol brasileiro polêmica podcast",
    "jogador famoso entrevista podcast",
    "ex jogador entrevista podcast polêmica",
    "Raiam Santos polêmica podcast",
    "Raiam Santos entrevista podcast",
    "Ruyter polêmica podcast",
    "Ruyter entrevista podcast",
]

GLOBAL_QUERIES = [
    "Joe Rogan Experience interview",
    "Theo Von podcast interview",
    "This Past Weekend interview",
    "Impaulsive podcast interview",
    "Piers Morgan interview",
    "Hot Ones interview",
    "Club Shay Shay interview",
    "Lex Fridman Podcast interview",
    "Diary of a CEO interview",
]

LOW_QUALITY_REJECT_TERMS = {
    "unimed", "rádio jota", "radio jota", "rádio carbo", "radio carbo",
    "arapuan verdade", "entrevista dr.", "entrevista doutor", "dr. ",
    "dra. ", "programa local", "prefeitura", "câmara municipal",
    "camara municipal", "assembleia legislativa", "institucional",
    "palestra institucional", "audiência pública", "audiencia publica",
}

GAME_REJECT_TERMS = {
    "gameplay", "walkthrough", "modern warfare", "call of duty", "mw2",
    "mw4", "unreal engine", "ign", "games on", "first games", "game",
}

MUSIC_REJECT_TERMS = {
    "official video", "music video", "lyrics", "trailer", "teaser",
    "clipe oficial", "música", "musica", "videoclipe", "lemonade",
    "feat.", "ft.",
}

SHORTS_REJECT_TERMS = {
    "#shorts", "shorts", "shortvideo", "shorts podcast",
}

REACT_REJECT_TERMS = {"react:", "react", "reação", "reacao", "reacts"}

FAN_CLIP_REJECT_TERMS = {
    "fan clip", "fan edit", "compilado", "compilação", "compilacao",
    "melhores momentos", "highlights",
}

PODCAST_STRONG_TERMS = {
    "flow", "podpah", "inteligência ltda", "inteligencia ltda",
    "ticaracaticast", "venus", "vênus", "papo de elite", "à deriva",
    "a deriva", "primocast", "redcast", "the noite", "programa do joão",
    "programa do joao", "ciência sem fim", "ciencia sem fim", "os sócios",
    "os socios", "cara a tapa", "joe rogan", "theo von", "lex fridman",
    "piers morgan", "hot ones", "club shay shay", "achismos tv",
    "achismos podcast", "achismos", "nômade raiz", "nomade raiz",
    "rango brabo", "quebrada fc", "podpah visita", "podpah de verão",
    "podpah de verao",
}

EDITORIAL_POSITIVE_TERMS = {
    "entrevista", "polêmica", "polemica", "bastidores", "famoso",
    "jogador", "ex jogador", "neymar", "copa do mundo", "raiam",
    "ruyter", "monark", "vilela", "joão kléber", "joao kleber",
    "história", "historia", "engraçada", "engracada", "humor",
    "revelou", "conversa", "podcast", "interview", "controversy",
    "backstage", "revealed", "relato", "perrengue", "viagem", "cultura",
    "experiência", "experiencia", "debate", "opinião", "opiniao",
    "curiosidade", "curiosidades", "perigo", "perigoso", "perigosos",
    "mundo", "realidade", "favela", "futebol", "empresário",
    "empresario", "fortuna", "crime", "ciência", "ciencia",
    "comportamento", "sociedade", "histórias", "historias",
}

PODCAST_INTENT_TERMS = {
    "podcast", "entrevista", "interview", "show", "cast", "conversa",
    "cortes", "corte",
}

CUTTABLE_FORMAT_TERMS = PODCAST_INTENT_TERMS | {
    "programa", "quadro", "história", "historia", "histórias", "historias",
    "relato", "perrengue", "bastidores", "viagem", "storytelling",
    "cultura", "mundo", "curiosidade", "curiosidades", "debate",
    "opinião", "opiniao", "análise", "analise", "experiência",
    "experiencia", "visita", "rango brabo", "quebrada fc", "achismos",
    "nômade raiz", "nomade raiz",
}


def main() -> None:
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-discovery", action="store_true")
    args = parser.parse_args()

    if not config.PODCAST_DISCOVERY_ENABLED:
        print("PODCAST DISCOVERY desativado por config.")
        return

    history = VideoHistoryService()
    history_data = history._read()
    priority = ProcessingPriorityService()
    key_manager = KeyRotationManager(config.YOUTUBE_API_KEYS_LIST)
    if not key_manager.current_key():
        print("YouTube API key ausente. Discovery não executado.")
        return

    markets = set(config.PODCAST_DISCOVERY_MARKETS)
    queries: list[tuple[str, str]] = []
    if "BR" in markets:
        queries.extend(("BR", query) for query in BR_QUERIES)
        queries.extend(("BR", query) for query in BR_TREND_QUERIES)
    if "GLOBAL" in markets:
        queries.extend(("GLOBAL", query) for query in GLOBAL_QUERIES)

    published_after = datetime.now(UTC) - timedelta(days=config.PODCAST_DISCOVERY_DAYS_BACK)
    found: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    errors: list[str] = []

    for market, query in queries:
        if len(found) >= config.PODCAST_DISCOVERY_MAX_RESULTS * 2:
            break
        videos, query_rejected, error = _search_query(key_manager, market, query, published_after)
        rejected.extend(query_rejected)
        if error:
            errors.append(error)
            if youtube_errors.QUOTA_EXHAUSTED:
                break
        for video in videos:
            block_reason = _discovery_block_reason(
                video["video_id"],
                video,
                history_data,
                force=args.force_discovery,
            )
            if block_reason:
                rejected.append({**video, "reason": block_reason})
                continue
            found.setdefault(video["video_id"], video)

    selected, rejected_by_selection = _select_diverse_videos(
        list(found.values()),
        priority,
        history_data,
        force=args.force_discovery,
    )
    rejected.extend(rejected_by_selection)

    enqueued: list[dict[str, Any]] = []
    skipped_existing = 0
    for item in selected:
        block_reason = _discovery_block_reason(
            item["video_id"],
            item,
            history._read(),
            force=args.force_discovery,
        )
        if block_reason:
            rejected.append({**item, "reason": block_reason})
            skipped_existing += 1
            continue
        if item.get("editorial_fit_score", 0) <= 0 or item.get("combined_discovery_score", 0) <= 0:
            rejected.append({**item, "reason": "score editorial/discovery zerado"})
            continue
        source_video = SourceVideo(**item["source_video"])
        was_enqueued = history.enqueue_video(source_video, None)
        if was_enqueued:
            _annotate_history(history, source_video.video_id, item)
            enqueued.append(item)
        else:
            skipped_existing += 1

    report_paths = _write_report(
        found=list(found.values()),
        selected=selected,
        enqueued=enqueued,
        rejected=rejected,
        skipped_existing=skipped_existing,
        errors=errors,
    )

    print("PODCAST DISCOVERY BATCH")
    print(f"Queries BR base: {len(BR_QUERIES)}")
    print(f"Queries BR trend: {len(BR_TREND_QUERIES)}")
    if "BR" in markets:
        print("BR_TREND_QUERIES: ativo no fluxo")
    print(f"Encontrados: {len(found)}")
    print(f"Selecionados: {len(selected)}")
    print(f"Enfileirados: {len(enqueued)}")
    print(f"Já existentes/ignorados: {skipped_existing}")
    print(f"Rejeitados: {len(rejected)}")
    if errors:
        print("Erros:")
        for error in errors[:5]:
            print(f"- {error}")
    print(f"Markdown: {report_paths['md']}")
    print(f"JSON: {report_paths['json']}")
    print("")
    print("Top vídeos enfileirados:")
    for item in enqueued[:10]:
        print(
            f"- combined {item['combined_discovery_score']:.2f} | "
            f"editorial {item['editorial_fit_score']:.2f} | "
            f"priority {item['processing_priority_score']:.2f} | "
            f"{item['duration_seconds']}s | "
            f"{item['channel_title']} | {item['title']} | {item['url']}"
        )
    if rejected:
        print("")
        print("Exemplos rejeitados:")
        for item in rejected[:10]:
            print(f"- {item.get('reason')} | {item.get('title', '')} | {item.get('url', '')}")


def _search_query(
    key_manager: KeyRotationManager,
    market: str,
    query: str,
    published_after: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    rejected: list[dict[str, Any]] = []
    while key_manager.current_key():
        try:
            youtube = build("youtube", "v3", developerKey=key_manager.current_key())
            search_response = (
                youtube.search()
                .list(
                    part="id",
                    q=query,
                    type="video",
                    order="date",
                    maxResults=8,
                    publishedAfter=published_after.isoformat().replace("+00:00", "Z"),
                    safeSearch="moderate",
                    relevanceLanguage="pt" if market == "BR" else "en",
                    regionCode="BR" if market == "BR" else "US",
                )
                .execute()
            )
            video_ids = [
                item["id"]["videoId"]
                for item in search_response.get("items", [])
                if item.get("id", {}).get("videoId")
            ]
            if not video_ids:
                return [], rejected, ""
            return _fetch_details(youtube, video_ids, market, query)
        except Exception as exc:
            if is_quota_error(exc):
                if key_manager.rotate():
                    continue
                mark_quota_exhausted()
                return [], rejected, "quota YouTube esgotada durante podcast discovery"
            return [], rejected, f"{query}: {sanitize_youtube_error(exc)}"
    return [], rejected, "sem chave YouTube disponível"


def _fetch_details(
    youtube: object,
    video_ids: list[str],
    market: str,
    query: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    response = (
        youtube.videos()
        .list(part="snippet,statistics,contentDetails,status", id=",".join(video_ids))
        .execute()
    )
    videos: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in response.get("items", []):
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        details = item.get("contentDetails", {})
        status = item.get("status", {})
        video_id = item.get("id", "")
        title = snippet.get("title", "")
        channel_title = snippet.get("channelTitle", "")
        duration_seconds = _duration_seconds(details.get("duration"))
        view_count = _to_int(statistics.get("viewCount"))
        like_count = _to_int(statistics.get("likeCount"))
        comment_count = _to_int(statistics.get("commentCount"))
        published_at = _parse_datetime(snippet.get("publishedAt"))
        url = f"https://www.youtube.com/watch?v={video_id}"
        reason = _reject_reason(title, channel_title, duration_seconds)
        if reason:
            rejected.append({"title": title, "url": url, "reason": reason, "query": query})
            continue
        engagement_score = _engagement_score(view_count, like_count, comment_count, published_at)
        source_video = {
            "video_id": video_id,
            "title": title,
            "channel_title": channel_title,
            "url": url,
            "published_at": published_at,
            "view_count": view_count,
            "like_count": like_count,
            "comment_count": comment_count,
            "duration_seconds": duration_seconds,
            "engagement_score": engagement_score,
            "license": status.get("license"),
        }
        video = {
            "video_id": video_id,
            "title": title,
            "channel_title": channel_title,
            "url": url,
            "market": market,
            "query": query,
            "published_at": published_at.isoformat() if published_at else "",
            "view_count": view_count,
            "like_count": like_count,
            "comment_count": comment_count,
            "duration_seconds": duration_seconds,
            "engagement_score": engagement_score,
            "source_video": source_video,
        }
        videos.append(video)
    return videos, rejected, ""


def _select_diverse_videos(
    videos: list[dict[str, Any]],
    priority: ProcessingPriorityService,
    history_data: dict[str, dict[str, Any]],
    force: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rejected: list[dict[str, Any]] = []
    for video in videos:
        score, reason = priority.score_video(
            {
                **video,
                "channel_name": video["channel_title"],
                "status": "queued",
            }
        )
        video["processing_priority_score"] = score
        video["processing_priority_reason"] = reason
        editorial_score, editorial_reasons = _editorial_fit_score(video)
        combined_score = (score * 0.55) + (editorial_score * 0.45)
        video["editorial_fit_score"] = round(editorial_score, 2)
        video["editorial_fit_reasons"] = editorial_reasons
        video["combined_discovery_score"] = round(combined_score, 2)
        video["topic_bucket"] = _topic_bucket(video)
    videos.sort(
        key=lambda item: (
            item["combined_discovery_score"],
            item["editorial_fit_score"],
            item["processing_priority_score"],
            item["comment_count"],
            item["view_count"],
        ),
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    per_channel: dict[str, int] = defaultdict(int)
    per_market: dict[str, int] = defaultdict(int)
    per_bucket: dict[str, int] = defaultdict(int)
    for video in videos:
        block_reason = _discovery_block_reason(
            video["video_id"],
            video,
            history_data,
            force=force,
        )
        if block_reason:
            rejected.append({**video, "reason": block_reason})
            continue
        if video["editorial_fit_score"] <= 0:
            rejected.append({**video, "reason": "editorial_fit_score zerado"})
            continue
        if video["combined_discovery_score"] <= 0:
            rejected.append({**video, "reason": "combined_discovery_score zerado"})
            continue
        if len(selected) >= config.PODCAST_DISCOVERY_MAX_RESULTS:
            rejected.extend(
                {**item, "reason": "limite maximo do batch"} for item in videos[videos.index(video):]
            )
            break
        channel_key = video["channel_title"].lower()
        if per_channel[channel_key] >= config.PODCAST_DISCOVERY_MAX_PER_CHANNEL:
            rejected.append({**video, "reason": "limite por canal"})
            continue
        if per_bucket[video["topic_bucket"]] >= 4:
            rejected.append({**video, "reason": f"limite por bucket: {video['topic_bucket']}"})
            continue
        if video["editorial_fit_score"] < 4.5:
            rejected.append({**video, "reason": "editorial_fit_score baixo"})
            continue
        if video["processing_priority_score"] < 4:
            rejected.append({**video, "reason": "processing_priority_score < 4"})
            continue
        selected.append(video)
        per_channel[channel_key] += 1
        per_market[video["market"]] += 1
        per_bucket[video["topic_bucket"]] += 1
    return selected, rejected


def _annotate_history(history: VideoHistoryService, video_id: str, item: dict[str, Any]) -> None:
    data = history._read()
    record = data.get(video_id)
    if not record:
        return
    record["discovery_source"] = "podcast_discovery_batch"
    record["discovery_market"] = item["market"]
    record["discovery_query"] = item["query"]
    record["topic_bucket"] = item["topic_bucket"]
    record["editorial_fit_score"] = item["editorial_fit_score"]
    record["editorial_fit_reasons"] = item["editorial_fit_reasons"]
    record["combined_discovery_score"] = item["combined_discovery_score"]
    record["processing_priority_score"] = item["processing_priority_score"]
    record["processing_priority_reason"] = item["processing_priority_reason"]
    record["updated_at"] = datetime.utcnow().isoformat()
    data[video_id] = record
    history._write(data)


def _write_report(
    found: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    enqueued: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    skipped_existing: int,
    errors: list[str],
) -> dict[str, str]:
    reports_dir = config.STORAGE_TRENDS_DIR.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    json_path = reports_dir / f"podcast_discovery_report_{timestamp}.json"
    md_path = reports_dir / f"podcast_discovery_report_{timestamp}.md"
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "found_count": len(found),
        "selected_count": len(selected),
        "enqueued_count": len(enqueued),
        "rejected_count": len(rejected),
        "skipped_existing": skipped_existing,
        "errors": errors,
        "found": _json_safe(found),
        "selected": _json_safe(selected),
        "enqueued": _json_safe(enqueued),
        "rejected": _json_safe(rejected),
    }
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    with md_path.open("w", encoding="utf-8") as file:
        file.write(_markdown_report(payload))
    return {"json": str(json_path), "md": str(md_path)}


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# ClipRadar Podcast Discovery Report",
        "",
        f"Generated at: {payload['generated_at']}",
        f"Found: {payload['found_count']}",
        f"Selected: {payload['selected_count']}",
        f"Enqueued: {payload['enqueued_count']}",
        f"Rejected: {payload['rejected_count']}",
        f"Skipped existing: {payload['skipped_existing']}",
        "",
        "## Enqueued",
        "",
    ]
    for item in payload["enqueued"]:
        lines.extend(_video_lines(item))
    lines.extend(["## Rejected", ""])
    for item in payload["rejected"][:50]:
        lines.append(f"- {item.get('reason', '')}: {item.get('title', '')} ({item.get('url', '')})")
    if payload["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in payload["errors"])
    return "\n".join(lines)


def _video_lines(item: dict[str, Any]) -> list[str]:
    return [
        f"### {item.get('title', '')}",
        "",
        f"Channel: {item.get('channel_title', '')}",
        f"Market: {item.get('market', '')}",
        f"Query: {item.get('query', '')}",
        f"Duration: {item.get('duration_seconds', 0)}",
        f"Views: {item.get('view_count', 0)}",
        f"Comments: {item.get('comment_count', 0)}",
        f"Processing Priority Score: {item.get('processing_priority_score', 0)}",
        f"Editorial Fit Score: {item.get('editorial_fit_score', 0)}",
        f"Combined Discovery Score: {item.get('combined_discovery_score', 0)}",
        f"Topic Bucket: {item.get('topic_bucket', '')}",
        f"Priority Reason: {item.get('processing_priority_reason', '')}",
        f"Editorial Reasons: {', '.join(item.get('editorial_fit_reasons', []))}",
        f"URL: {item.get('url', '')}",
        "",
    ]


def _reject_reason(title: str, channel_title: str, duration_seconds: int) -> str:
    text = f"{title} {channel_title}".lower()
    if duration_seconds < config.PODCAST_DISCOVERY_MIN_DURATION_SECONDS:
        return f"duration < {config.PODCAST_DISCOVERY_MIN_DURATION_SECONDS}s"
    for term in SHORTS_REJECT_TERMS:
        if term in text:
            return f"shorts rejeitado: {term}"
    for term in MUSIC_REJECT_TERMS:
        if term in text:
            return f"música/trailer/clipe rejeitado: {term}"
    for term in GAME_REJECT_TERMS:
        if term in text:
            return f"gameplay/jogo rejeitado: {term}"
    for term in LOW_QUALITY_REJECT_TERMS:
        if term in text:
            return f"local/institucional rejeitado: {term}"
    for term in FAN_CLIP_REJECT_TERMS:
        if term in text:
            return f"fan clip/compilado rejeitado: {term}"
    for term in REACT_REJECT_TERMS:
        if term in text:
            return f"react/reação rejeitado: {term}"
    if not any(term in text for term in CUTTABLE_FORMAT_TERMS):
        return "não parece formato cortável"
    return ""


def _discovery_block_reason(
    video_id: str,
    video: dict[str, Any],
    history_data: dict[str, dict[str, Any]],
    force: bool = False,
) -> str:
    if force:
        return ""
    record = history_data.get(video_id, {})
    status = str(record.get("status") or "")
    blocked_statuses = {
        "done", "processed", "source_rejected", "weak_source_reviewed",
        "bad_source", "processing",
    }
    if status in blocked_statuses:
        return f"histórico bloqueado: status={status}"
    if status == "needs_manual_review" and record.get("should_continue_video_review") is False:
        return "histórico bloqueado: needs_manual_review sem continuar revisão"
    if record.get("source_quality_tier") == "bad_source":
        return "histórico bloqueado: bad_source"
    if record.get("should_continue_video_review") is False:
        return "histórico bloqueado: should_continue_video_review=false"
    if (config.STORAGE_TRANSCRIPTS_DIR / f"{video_id}.json").exists():
        return "já possui transcript local"
    if (config.STORAGE_CLIPS_DIR / f"{video_id}_clips.json").exists():
        return "já possui clips local"
    if float(video.get("editorial_fit_score") or 1.0) <= 0:
        return "editorial_fit_score zerado"
    if float(video.get("combined_discovery_score") or 1.0) <= 0:
        return "combined_discovery_score zerado"
    return ""


def _editorial_fit_score(video: dict[str, Any]) -> tuple[float, list[str]]:
    text = f"{video.get('title', '')} {video.get('channel_title', '')}".lower()
    duration = int(video.get("duration_seconds") or 0)
    views = int(video.get("view_count") or 0)
    comments = int(video.get("comment_count") or 0)
    score = 0.0
    reasons: list[str] = []

    strong_sources = sorted(term for term in PODCAST_STRONG_TERMS if term in text)
    if strong_sources:
        score += 3.5
        reasons.append(f"fonte forte: {', '.join(strong_sources[:3])}")

    positive_terms = sorted(term for term in EDITORIAL_POSITIVE_TERMS if term in text)
    if positive_terms:
        score += min(3.0, 0.7 * len(positive_terms))
        reasons.append(f"sinais editoriais: {', '.join(positive_terms[:5])}")

    if 480 <= duration <= 10800:
        score += 1.4
        reasons.append("duração boa para formato cortável")
    elif duration > 10800:
        score += 0.4
        reasons.append("duração muito longa, mas aproveitável")
    else:
        score -= 4.0
        reasons.append("duração abaixo do mínimo")

    if comments >= 500:
        score += 1.2
        reasons.append("comentários fortes")
    elif comments >= 100:
        score += 0.7
        reasons.append("comentários relevantes")
    elif comments < 20:
        score -= 0.8
        reasons.append("poucos comentários")

    if views >= 300_000:
        score += 1.2
        reasons.append("views fortes")
    elif views >= 50_000:
        score += 0.7
        reasons.append("views relevantes")
    elif views < 5_000:
        score -= 0.7
        reasons.append("baixo volume de views")

    negative_categories = [
        (LOW_QUALITY_REJECT_TERMS, "sinal local/institucional"),
        (GAME_REJECT_TERMS, "sinal de gameplay/jogo"),
        (MUSIC_REJECT_TERMS, "sinal de música/trailer"),
        (FAN_CLIP_REJECT_TERMS, "sinal de fan clip/compilado"),
    ]
    for terms, label in negative_categories:
        matches = sorted(term for term in terms if term in text)
        if matches:
            score -= 4.0
            reasons.append(f"{label}: {', '.join(matches[:3])}")
    if "react" in text:
        score -= 2.0
        reasons.append("react reduzido")
    if not _has_strong_cuttable_signal(text) and not positive_terms:
        score -= 2.0
        reasons.append("canal desconhecido/título genérico")

    return max(0.0, min(10.0, round(score, 2))), reasons or ["sem sinais editoriais fortes"]


def _has_strong_cuttable_signal(text: str) -> bool:
    return any(term in text for term in PODCAST_STRONG_TERMS | CUTTABLE_FORMAT_TERMS)


def _topic_bucket(video: dict[str, Any]) -> str:
    text = f"{video['title']} {video['channel_title']}".lower()
    if any(term in text for term in {"viagem", "nômade", "nomade", "países", "paises", "mundo", "cultura", "perrengue"}):
        return "viagem/storytelling"
    if any(term in text for term in {"ciência", "ciencia", "comportamento", "sociedade", "achismos", "tecnologia", "tech", "lex fridman"}):
        return "ciencia/comportamento"
    if any(term in text for term in {"dinheiro", "business", "empresa", "mercado", "primo", "socios", "sócios"}):
        return "negocios/dinheiro"
    if any(term in text for term in {"neymar", "futebol", "jogador", "ex jogador", "copa do mundo", "flamengo", "corinthians", "quebrada fc"}):
        return "futebol"
    if any(term in text for term in {"celebrity", "famous", "hot ones", "club shay shay"}):
        return "global/celebrity"
    if any(term in text for term in {"política", "politica", "piers", "opinião", "opiniao"}):
        return "politica/opiniao"
    if any(term in text for term in {"crime", "polícia", "policia", "segurança", "investigation"}):
        return "crime/seguranca"
    if any(term in text for term in {"humor", "comed", "funny", "the noite", "theo von", "famoso"}):
        return "humor/famoso"
    if any(term in text for term in {"história", "historia", "histórias", "historias", "relato", "story", "curious", "curios"}):
        return "historias/relatos"
    return "podcast/entrevista"


def _duration_seconds(value: str | None) -> int:
    if not value:
        return 0
    try:
        return int(isodate.parse_duration(value).total_seconds())
    except Exception:
        return 0


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _engagement_score(
    view_count: int,
    like_count: int,
    comment_count: int,
    published_at: datetime | None,
) -> float:
    if view_count <= 0:
        return 0.0
    interaction_rate = (like_count + (comment_count * 2)) / view_count
    volume_score = min(4.0, log10(view_count + 1) / 2)
    engagement_score = min(4.0, interaction_rate * 120)
    recency_score = 1.0
    if published_at:
        age_days = max(0, (datetime.now(UTC) - published_at).days)
        if age_days <= 7:
            recency_score = 2.0
        elif age_days <= 30:
            recency_score = 1.5
    return round(min(10.0, volume_score + engagement_score + recency_score), 2)


def _json_safe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe_items: list[dict[str, Any]] = []
    for item in items:
        safe = {}
        for key, value in item.items():
            if key == "source_video":
                safe[key] = _json_safe([value])[0]
            elif isinstance(value, datetime):
                safe[key] = value.isoformat()
            else:
                safe[key] = value
        safe_items.append(safe)
    return safe_items


def _to_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def configure_output() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


if __name__ == "__main__":
    main()
