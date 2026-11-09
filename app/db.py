"""Configuração do Tortoise ORM, usada pela API, pelo Aerich e pelo seed."""

from app.config import get_settings

TORTOISE_ORM = {
    "connections": {"default": get_settings().database_url},
    "apps": {
        "models": {
            "models": ["app.models", "aerich.models"],
            "default_connection": "default",
        }
    },
    "use_tz": True,
    "timezone": "America/Maceio",
}
