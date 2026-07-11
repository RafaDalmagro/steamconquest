import time
from typing import Any, Callable


class TTLCache:
    """Cache em memória com expiração por chave. Volátil e por processo.

    Não é banco de dados: serve apenas para reduzir chamadas à Steam dentro de
    uma janela curta. O relógio é injetável para tornar a expiração testável.
    """

    def __init__(self, now: Callable[[], float] = time.monotonic):
        self._now = now
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if self._now() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: float) -> None:
        self._store[key] = (self._now() + ttl, value)
