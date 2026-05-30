import re


QUOTA_EXHAUSTED = False
ROTATION_EVENTS: list[tuple[str, bool]] = []


class KeyRotationManager:
    def __init__(self, keys: list[str]) -> None:
        self._keys = list(keys)
        self._current = 0
        self.all_exhausted = False

    def current_key(self) -> str:
        if not self._keys:
            return ""
        return self._keys[self._current]

    def rotate(self) -> bool:
        """Tenta próxima chave. Retorna False se esgotou todas."""
        self._current += 1
        if self._current >= len(self._keys):
            self.all_exhausted = True
            return False
        return True

    @property
    def current_index(self) -> int:
        return min(self._current + 1, len(self._keys))

    @property
    def total(self) -> int:
        return len(self._keys)


def sanitize_youtube_error(error: Exception) -> str:
    message = str(error)
    message = re.sub(r"key=[^&\s]+", "key=[redacted]", message)
    return message


def is_quota_error(error: Exception) -> bool:
    message = str(error).lower()
    quota_patterns = [
        "quotaexceeded",
        "dailylimitexceeded",
        "ratelimitexceeded",
        "exceeded your quota",
        "quota",
        "rate limit",
    ]
    return any(pattern in message for pattern in quota_patterns)


def mark_quota_exhausted() -> None:
    global QUOTA_EXHAUSTED
    QUOTA_EXHAUSTED = True


def record_rotation_event(message: str, success: bool) -> None:
    ROTATION_EVENTS.append((message, success))


def get_rotation_events() -> list[tuple[str, bool]]:
    return list(ROTATION_EVENTS)


def reset_quota_state() -> None:
    global QUOTA_EXHAUSTED
    QUOTA_EXHAUSTED = False
    ROTATION_EVENTS.clear()
