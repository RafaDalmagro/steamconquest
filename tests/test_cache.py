from app.core.cache import TTLCache


def test_valor_armazenado_e_recuperado_dentro_do_ttl():
    cache = TTLCache()

    cache.set("k", "v", ttl=10)

    assert cache.get("k") == "v"


def test_chave_inexistente_retorna_none():
    cache = TTLCache()

    assert cache.get("ausente") is None


def test_valor_expira_apos_o_ttl():
    relogio = {"agora": 1000.0}
    cache = TTLCache(now=lambda: relogio["agora"])
    cache.set("k", "v", ttl=10)

    relogio["agora"] = 1011.0

    assert cache.get("k") is None
