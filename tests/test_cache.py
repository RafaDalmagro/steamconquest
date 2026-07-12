from app.core.cache import TTLCache


def test_valor_armazenado_e_recuperado_dentro_do_ttl():
    cache = TTLCache()

    cache.set("k", "v", ttl=10)

    assert cache.get("k") == "v"


def test_chave_inexistente_retorna_none():
    cache = TTLCache()

    assert cache.get("ausente") is None


def test_cache_nao_cresce_alem_do_teto():
    # O steamid é input público: sem teto, quem chamar com IDs sempre novos faz o
    # dict crescer sem limite (as entradas nunca são relidas, logo nunca expiram
    # de fato) até derrubar o processo.
    cache = TTLCache(maxsize=3)

    for i in range(10):
        cache.set(f"k{i}", i, ttl=300)

    assert cache.tamanho <= 3


def test_ao_estourar_o_teto_descarta_a_entrada_mais_antiga():
    cache = TTLCache(maxsize=2)
    cache.set("velha", 1, ttl=300)
    cache.set("media", 2, ttl=300)

    cache.set("nova", 3, ttl=300)

    assert cache.get("velha") is None
    assert cache.get("media") == 2
    assert cache.get("nova") == 3


def test_entrada_expirada_e_descartada_antes_da_mais_antiga():
    # Expirada é lixo puro: sai primeiro, poupando uma entrada ainda válida.
    relogio = {"agora": 1000.0}
    cache = TTLCache(maxsize=2, now=lambda: relogio["agora"])
    cache.set("curta", 1, ttl=5)
    cache.set("longa", 2, ttl=300)

    relogio["agora"] = 1010.0  # "curta" expirou
    cache.set("nova", 3, ttl=300)

    assert cache.get("longa") == 2  # sobreviveu: quem saiu foi a expirada
    assert cache.get("nova") == 3


def test_valor_expira_apos_o_ttl():
    relogio = {"agora": 1000.0}
    cache = TTLCache(now=lambda: relogio["agora"])
    cache.set("k", "v", ttl=10)

    relogio["agora"] = 1011.0

    assert cache.get("k") is None
