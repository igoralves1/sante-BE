from typing import TypeVar

from fastapi import HTTPException
from tortoise.models import Model

T = TypeVar("T", bound=Model)


async def achar(modelo: type[T], id: str, nome: str) -> T:
    obj = await modelo.get_or_none(id=id)
    if obj is None:
        raise HTTPException(404, f"{nome} {id} não encontrado.")
    return obj


def validar_mes(mes: str) -> str:
    try:
        ano, mm = (int(x) for x in mes.split("-"))
        assert 1 <= mm <= 12 and 2000 <= ano <= 2100
    except (ValueError, AssertionError):
        raise HTTPException(422, "Use o mês no formato AAAA-MM.") from None
    return f"{ano:04d}-{mm:02d}"
