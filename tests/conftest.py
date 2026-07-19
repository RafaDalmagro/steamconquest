import os

# No topo do módulo, e não numa fixture: `test_routes.py` monta o app durante a
# **importação**, que acontece antes de qualquer fixture rodar. O pytest importa
# o conftest primeiro, então este é o único ponto que chega a tempo.
os.environ.setdefault("STEAM_API_KEY", "chave-de-teste")
os.environ["ANTHROPIC_API_KEY"] = "chave-de-teste-ia"
os.environ["GEMINI_API_KEY"] = "chave-de-teste-gemini"

# A suíte NÃO lê o `.env` do desenvolvedor.
#
# Duas razões, e a segunda foi descoberta na prática: adicionar uma
# `GEMINI_API_KEY` real ao `.env` quebrou o teste que prova que o boot falha sem
# ela — o `monkeypatch.delenv` tirava a variável do ambiente e o `.env` a
# devolvia por baixo.
#
# 1. **Determinismo.** Config local não pode fazer teste passar (nem falhar).
#    Teste que depende do `.env` da máquina passa pelo motivo errado — mesma
#    classe de defeito do `tsc --noEmit` que checava zero arquivos.
# 2. **Custo.** Sem o `.env`, é estruturalmente impossível um teste pegar uma
#    chave real e gastar dinheiro. Antes isso dependia só da precedência de env
#    var sobre arquivo, que é uma garantia mais fraca.
from app.config import Settings  # noqa: E402

Settings.model_config["env_file"] = None
