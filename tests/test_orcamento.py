from app.core.orcamento import OrcamentoDeIA

DIA = 86_400.0
DONO = "76561198082363621"
VISITANTE = "76561197960287930"


class Relogio:
    """Relógio injetável — a virada do dia precisa ser testável sem esperar."""

    def __init__(self, t: float = 0.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


def test_cota_do_dia_zera_na_virada():
    relogio = Relogio()
    orcamento = OrcamentoDeIA(por_dia=2, por_dia_do_dono=0, now=relogio)

    assert orcamento.consumir(VISITANTE)
    assert orcamento.consumir(VISITANTE)
    assert not orcamento.consumir(VISITANTE)

    relogio.t += DIA

    assert orcamento.consumir(VISITANTE)


def test_meio_dia_depois_ainda_e_o_mesmo_dia():
    # Janela fixa por dia UTC, não deslizante: meia jornada adiante continua
    # sendo o mesmo balde. Sem isto, "3 por dia" viraria "3 a cada 24h móveis",
    # que é mais permissivo do que o número anuncia.
    relogio = Relogio()
    orcamento = OrcamentoDeIA(por_dia=1, por_dia_do_dono=0, now=relogio)

    assert orcamento.consumir(VISITANTE)
    relogio.t += DIA / 2
    assert not orcamento.consumir(VISITANTE)


def test_cotas_do_dono_e_do_visitante_sao_independentes():
    relogio = Relogio()
    orcamento = OrcamentoDeIA(por_dia=1, por_dia_do_dono=1, dono=DONO, now=relogio)

    assert orcamento.consumir(VISITANTE)
    assert not orcamento.consumir(VISITANTE)
    assert orcamento.consumir(DONO)
    assert not orcamento.consumir(DONO)


def test_sem_dono_configurado_todos_caem_na_cota_global():
    # Default de produção quando OWNER_STEAMID não é preenchido: a reserva
    # simplesmente não existe, em vez de virar cota extra para alguém.
    relogio = Relogio()
    orcamento = OrcamentoDeIA(por_dia=1, por_dia_do_dono=99, now=relogio)

    assert orcamento.consumir(DONO)
    assert not orcamento.consumir(DONO)
