import time
from typing import Callable

_DIA = 86_400.0


class _CotaDiaria:
    """Contador de chamadas pagas que zera na virada do dia (UTC)."""

    def __init__(self, limite: int, now: Callable[[], float]):
        self._limite = limite
        self._now = now
        self._dia = int(now() // _DIA)
        self._gasto = 0

    def consumir(self) -> bool:
        dia = int(self._now() // _DIA)
        if dia != self._dia:
            self._dia = dia
            self._gasto = 0
        if self._gasto >= self._limite:
            return False
        self._gasto += 1
        return True


class OrcamentoDeIA:
    """Teto **de gasto** para as chamadas pagas — irmão do `TokenBucket`, não
    substituto dele.

    O bucket limita **rajada** (protege contra pico e contra o rate limit do
    provedor); este limita **acumulado no dia** (protege a fatura). A 10/min
    sustentados o bucket sozinho deixa passar ~14 mil chamadas por dia, que a
    ~$0.04 cada é ordem de centenas de dólares. Um não faz o trabalho do outro.

    Duas cotas separadas porque teto único tem um efeito ruim: um visitante (ou
    um bot) esgotando o dia tranca o dono fora do próprio app. A cota do dono é
    reserva, não privilégio — some do bolso junto com a global.

    ⚠️ **É volátil.** Vive no processo, então reinício zera o dia. Isso é
    aceitável só porque o teto de gasto do Console da Anthropic existe como
    garantia externa — essa sim sobrevive a deploy, a reinício e a bug daqui.
    Persistir o contador significaria banco, que o CLAUDE.md manda aprovar antes.

    O `steamid` do dono vem do env e é comparado ao da URL, que é **forjável**:
    quem souber o ID usa a reserva. Aceito porque o efeito é gastar cota alheia,
    não vazar dado — e o teto global continua valendo por cima.
    """

    def __init__(
        self,
        por_dia: int,
        por_dia_do_dono: int,
        dono: str | None = None,
        now: Callable[[], float] = time.time,
    ):
        self._dono = dono or None
        self._global = _CotaDiaria(por_dia, now)
        self._do_dono = _CotaDiaria(por_dia_do_dono, now)

    def consumir(self, steamid: str) -> bool:
        """Debita uma chamada paga da cota certa. False = orçamento do dia acabou.

        O dono cai na cota dele e **não** transborda para a global: transbordar
        faria a reserva virar cota extra, e o pior caso do mês deixaria de ser a
        soma anunciada.
        """
        if self._dono is not None and steamid == self._dono:
            return self._do_dono.consumir()
        return self._global.consumir()
