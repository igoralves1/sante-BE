from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração lida das variáveis de ambiente (ou do arquivo .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://sante:sante@localhost:5432/sante"
    # origens do front que podem chamar a API (separadas por vírgula)
    cors_origins: str = "https://igoralves1.github.io"
    # o front rodando na máquina (npm run dev, em qualquer porta)
    cors_origin_regex: str = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"
    # carrega seed/*.json quando o banco está vazio
    seed_on_start: bool = True

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
