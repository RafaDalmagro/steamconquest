from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração via ambiente. Segredos nunca em código (ver CLAUDE.md)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    steam_api_key: str
    steam_concurrency: int = 5
    http_timeout: float = 10.0
