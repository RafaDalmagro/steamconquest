import time
from typing import Callable


class TokenBucket:
    """Teto global de chamadas a um provedor externo, protegendo a **credencial**.

    Guarda a chave, não o processo: vale para qualquer chamador, e nenhum header
    forjado escapa dele. `burst` absorve a rajada legítima; `rate` sustenta o
    orçamento sustentado.

    Vive em `core/` (e não dentro de um cliente) porque há dois provedores com o
    mesmo problema e regimes de custo diferentes: a Steam gasta **cota**, a IA
    gasta **dinheiro**. A lógica é a mesma; os números, não — por isso cada
    cliente instancia o seu, com os seus limites.

    O relógio é injetável para tornar a recarga testável sem dormir.
    """

    def __init__(self, rate_per_minute: float, burst: int, now: Callable[[], float] = time.monotonic):
        self._rate = rate_per_minute / 60.0  # tokens por segundo
        self._capacity = float(burst)
        self._tokens = float(burst)
        self._now = now
        self._updated = now()

    def consume(self) -> bool:
        agora = self._now()
        self._tokens = min(
            self._capacity, self._tokens + (agora - self._updated) * self._rate
        )
        self._updated = agora
        if self._tokens < 1:
            return False
        self._tokens -= 1
        return True
