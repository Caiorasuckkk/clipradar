import re
import string
from collections import Counter


PUBLISHERS = {
    "ap news",
    "bbc",
    "cnn",
    "estadão",
    "estadao",
    "folha",
    "g1",
    "globo",
    "reuters",
    "terra",
    "uol",
}

LEADING_GENERIC_WORDS = {
    "aponta",
    "confira",
    "entenda",
    "how",
    "mostra",
    "new",
    "nova",
    "novo",
    "saiba",
    "see",
    "veja",
    "watch",
    "what",
    "why",
}

ENDING_GENERIC_WORDS = LEADING_GENERIC_WORDS | {
    "art",
    "made",
    "news",
    "sobre",
    "with",
}

STOPWORDS = {
    "a",
    "about",
    "after",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "com",
    "como",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "for",
    "from",
    "g1",
    "globo",
    "how",
    "in",
    "is",
    "na",
    "nas",
    "no",
    "nos",
    "noticias",
    "notícias",
    "o",
    "of",
    "on",
    "os",
    "para",
    "por",
    "que",
    "says",
    "the",
    "to",
    "uol",
    "um",
    "uma",
    "with",
}


def extract_keyword(title: str, max_words: int = 4) -> str:
    cleaned_title = _remove_publisher_suffix(title)
    cleaned_title = _remove_long_subtitle(cleaned_title)
    cleaned_title = _remove_excess_non_latin(cleaned_title)
    words = _candidate_words(cleaned_title)
    words = _remove_edge_generic_words(words)
    if _use_fallback(cleaned_title, words):
        return _trim_to_words(words, max_words=max_words)

    phrases = _phrases(words, max_words=max_words)
    if phrases:
        return _clean_final_keyword(phrases[0])

    return _trim_to_words(words, max_words=max_words)


def _remove_publisher_suffix(title: str) -> str:
    separators = [" - ", " | ", " – ", " — "]
    cleaned = title.strip()
    for separator in separators:
        if separator in cleaned:
            parts = [part.strip() for part in cleaned.split(separator) if part.strip()]
            if parts and parts[-1].lower() in PUBLISHERS:
                cleaned = separator.join(parts[:-1])
            else:
                cleaned = parts[0] if parts else cleaned

    publisher_pattern = r"\s*(?:-|—|–|\|)\s*(" + "|".join(re.escape(p) for p in PUBLISHERS) + r")$"
    return re.sub(publisher_pattern, "", cleaned, flags=re.IGNORECASE).strip()


def _remove_long_subtitle(title: str) -> str:
    if ":" not in title:
        return title
    before, after = [part.strip() for part in title.split(":", 1)]
    if len(after.split()) > 6 or len(before.split()) >= 2:
        return before
    return title


def _remove_excess_non_latin(text: str) -> str:
    text = text.replace('"', " ").replace("'", " ").replace("“", " ").replace("”", " ")
    text = re.sub(r"[^\w\sÀ-ÿ.,:;!?%$€£@#&()/+-]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _candidate_words(text: str) -> list[str]:
    translator = str.maketrans("", "", string.punctuation + "“”‘’")
    normalized = text.lower().translate(translator)
    normalized = re.sub(r"\s+", " ", normalized)
    return [
        word
        for word in normalized.split()
        if len(word) > 2 and word not in STOPWORDS and not word.isnumeric()
    ]


def _remove_edge_generic_words(words: list[str]) -> list[str]:
    cleaned = list(words)
    while cleaned and cleaned[0] in LEADING_GENERIC_WORDS:
        cleaned.pop(0)
    while cleaned and cleaned[-1] in ENDING_GENERIC_WORDS:
        cleaned.pop()
    return cleaned


def _use_fallback(cleaned_title: str, words: list[str]) -> bool:
    if len(words) < 2:
        return True
    if len(cleaned_title.split()) > 8 and len(words) > 8:
        return False
    return False


def _trim_to_words(words: list[str], max_words: int) -> str:
    useful_words = [word for word in words if len(word) >= 3]
    if not useful_words:
        return ""
    return _clean_final_keyword(" ".join(useful_words[:max_words]))


def _clean_final_keyword(keyword: str) -> str:
    keyword = re.sub(r"\s+", " ", keyword).strip(" -|—–.,:;\"'")
    words = keyword.split()
    words = _remove_edge_generic_words(words)
    if len("".join(words)) < 3:
        return ""
    if len(words) > 6:
        words = words[:6]
    keyword = " ".join(words)
    return keyword[:120].rsplit(" ", 1)[0] if len(keyword) > 120 and " " in keyword else keyword


def _phrases(words: list[str], max_words: int) -> list[str]:
    candidates: list[str] = []
    for size in range(min(max_words, len(words)), 1, -1):
        for index in range(0, len(words) - size + 1):
            phrase_words = words[index : index + size]
            candidates.append(" ".join(phrase_words))

    if not candidates:
        return []

    counts = Counter(candidates)
    return [
        phrase
        for phrase, _ in sorted(
            counts.items(),
            key=lambda item: (item[1], len(item[0])),
            reverse=True,
        )
    ]
