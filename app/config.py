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


def load_settings() -> Settings:
    """Carrega Settings do ambiente/.env.

    O type checker não sabe que campos obrigatórios (steam_api_key) vêm do env,
    então acusa argumento ausente. O ignore fica aqui, num ponto só.
    """
    return Settings()  # pyright: ignore[reportCallIssue]
