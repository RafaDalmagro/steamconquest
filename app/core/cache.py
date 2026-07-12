import time
from typing import Any, Callable

# Teto de entradas. O steamid é input público (vem da URL), então o espaço de
# chaves é controlado por quem chama: sem teto, IDs sempre novos fazem o dict
# crescer sem limite — entradas nunca relidas nunca expiram — até derrubar o
# processo. 5000 cobre com folga o uso real (poucos perfis × poucos appids).
_MAXSIZE = 5_000


class TTLCache:
    """Cache em memória com expiração por chave e teto de tamanho. Volátil e por
    processo.

    Não é banco de dados: serve apenas para reduzir chamadas à Steam dentro de
    uma janela curta. O relógio é injetável para tornar a expiração testável.
    """

    def __init__(
        self, now: Callable[[], float] = time.monotonic, maxsize: int = _MAXSIZE
    ):
        self._now = now
        self._maxsize = maxsize
        self._store: dict[str, tuple[float, Any]] = {}

    @property
    def tamanho(self) -> int:
        return len(self._store)

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
        if key not in self._store and self.tamanho >= self._maxsize:
            self._descarta_uma()
        self._store[key] = (self._now() + ttl, value)

    def _descarta_uma(self) -> None:
        # Expirada é lixo puro: sai antes de qualquer entrada ainda válida.
        agora = self._now()
        for key, (expires_at, _) in self._store.items():
            if agora >= expires_at:
                del self._store[key]
                return
        # Nenhuma expirada: cai na mais antiga (dict preserva ordem de inserção).
        del self._store[next(iter(self._store))]
