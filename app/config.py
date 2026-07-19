from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração via ambiente. Segredos nunca em código (ver CLAUDE.md)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    steam_api_key: str
    # dev é o default seguro: a máquina local não precisa declarar nada.
    environment: Literal["dev", "prod"] = "dev"
    cors_origins: str = ""
    steam_concurrency: int = 5
    http_timeout: float = 10.0
    # Teto de saída para a Steam, protegendo a quota da chave (~100k/dia ≈ 70/min
    # sustentados). O burst absorve o load de uma biblioteca grande, que dispara
    # uma chamada de conquistas por jogo.
    steam_rate_per_minute: float = 70.0
    steam_rate_burst: int = 500

    # Provedor ativo. Um por vez: fallback automático é outra feature (§1 da
    # spec-design-provedor-de-ia-plugavel). Lido no boot — input público não
    # escolhe onde o dinheiro é gasto (CON-131).
    ai_provider: Literal["anthropic", "gemini"] = "anthropic"

    # Configuração POR PROVEDOR, e não genérica, porque o valor correto depende
    # de qual está ativo e nada no .env diria isso. Trocar de provedor esquecendo
    # de reajustar um teto calibrado para o outro é o erro que custa caro.
    # As chaves usam os nomes que os SDKs leem por convenção.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"
    # Custo linear (~$0,05/dica): teto baixo.
    anthropic_daily_budget: int = 3
    anthropic_owner_daily_budget: int = 3

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    # Cota gratuita de 5.000 buscas/mês ≈ 1.666 dicas: teto generoso. Mas não
    # ilimitado — passada a cota, o Gemini cobra $14/1.000 contra $10 da
    # Anthropic, então aqui o teto protege contra um *degrau*, não contra custo
    # linear.
    gemini_daily_budget: int = 100
    gemini_owner_daily_budget: int = 50
    # Teto muito menor que o da Steam: lá se protege cota que renova, aqui se
    # protege fatura. `appid`/`apiname` vêm da URL, então este é o número que
    # separa "alguém abusou" de "alguém abusou e custou caro".
    # Bucket e orçamento fazem trabalhos diferentes: o bucket limita **rajada**
    # (protege do rate limit do provedor), o orçamento limita **acumulado no
    # dia** (protege a fatura). A 10/min sustentados o bucket sozinho deixava
    # passar ~14 mil chamadas/dia — ordem de centenas de dólares.
    ai_rate_per_minute: float = 2.0
    ai_rate_burst: int = 5
    # Vazio = sem reserva; todos caem na cota global. Vem da URL e é forjável:
    # quem souber o ID usa a reserva. Aceito porque gasta cota, não vaza dado.
    owner_steamid: str = ""

    @property
    def daily_budget(self) -> int:
        """Teto do provedor ATIVO. Resolver aqui é o que impede o `lifespan` de
        ter um if de provedor — e o dono de esquecer de reajustar ao trocar."""
        return {
            "anthropic": self.anthropic_daily_budget,
            "gemini": self.gemini_daily_budget,
        }[self.ai_provider]

    @property
    def owner_daily_budget(self) -> int:
        return {
            "anthropic": self.anthropic_owner_daily_budget,
            "gemini": self.gemini_owner_daily_budget,
        }[self.ai_provider]

    @model_validator(mode="after")
    def _exige_a_chave_do_provedor_ativo(self):
        """Falha no boot, não no primeiro clique.

        Exigir as duas chaves obrigaria a ter conta nos dois fornecedores para
        rodar com um só. Não exigir nenhuma trocaria uma falha alta e imediata
        por um 500 no meio do uso.
        """
        chaves = {
            "anthropic": self.anthropic_api_key,
            "gemini": self.gemini_api_key,
        }
        if not chaves[self.ai_provider]:
            raise ValueError(
                f"AI_PROVIDER={self.ai_provider} exige "
                f"{self.ai_provider.upper()}_API_KEY definida"
            )
        return self


def load_settings() -> Settings:
    """Carrega Settings do ambiente/.env.

    O type checker não sabe que campos obrigatórios (steam_api_key) vêm do env,
    então acusa argumento ausente. O ignore fica aqui, num ponto só.
    """
    return Settings()  # pyright: ignore[reportCallIssue]
