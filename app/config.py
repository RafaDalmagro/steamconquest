from typing import Literal

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

    # Segredo, mesma disciplina da steam_api_key: só env, nunca no bundle ou log.
    anthropic_api_key: str
    # Default barato de propósito: esquecer a env var não pode virar conta cara
    # por acidente. Trocável por ambiente sem mudar código — o payload enviado é
    # o mínimo, válido em haiku-4-5 / sonnet-5 / opus-4-8 (CON-113).
    ai_model: str = "claude-haiku-4-5"
    # Teto muito menor que o da Steam: lá se protege cota que renova, aqui se
    # protege fatura. `appid`/`apiname` vêm da URL, então este é o número que
    # separa "alguém abusou" de "alguém abusou e custou caro".
    ai_rate_per_minute: float = 10.0
    ai_rate_burst: int = 20


def load_settings() -> Settings:
    """Carrega Settings do ambiente/.env.

    O type checker não sabe que campos obrigatórios (steam_api_key) vêm do env,
    então acusa argumento ausente. O ignore fica aqui, num ponto só.
    """
    return Settings()  # pyright: ignore[reportCallIssue]
