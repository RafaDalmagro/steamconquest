import os

# No topo do módulo, e não numa fixture: `test_routes.py` monta o app durante a
# **importação**, que acontece antes de qualquer fixture rodar. O pytest importa
# o conftest primeiro, então este é o único ponto que chega a tempo.
#
# Duas razões para existir, e a segunda é a que importa:
#
# 1. `Settings` exige `steam_api_key` e `anthropic_api_key`; sem elas os módulos
#    que montam o app na importação nem coletam.
# 2. **Variável de ambiente vence `.env`.** Então mesmo com uma chave real no
#    `.env` da máquina, a suíte roda com estas. É o que torna impossível um teste
#    gastar dinheiro por acidente — critério de validação da
#    `spec-design-dica-conquista-ia.md` §6.
os.environ.setdefault("STEAM_API_KEY", "chave-de-teste")
os.environ["ANTHROPIC_API_KEY"] = "chave-de-teste-ia"
