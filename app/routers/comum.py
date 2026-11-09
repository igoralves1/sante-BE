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


# respostas de erro para a documentação (/docs)
def _erro(codigo: int, descricao: str) -> dict:
    from app.schemas import Erro, ErroValidacao

    return {codigo: {"model": ErroValidacao if codigo == 422 else Erro, "description": descricao}}


ERRO_400 = _erro(400, "Pedido inválido (ex.: erro de sintaxe no SQL).")
ERRO_403 = _erro(403, "Recurso desligado neste servidor.")
ERRO_404 = _erro(404, "Registro não encontrado.")
ERRO_409 = _erro(409, "Conflito com dados existentes (nome repetido, turno já ocupado, registro em uso).")
ERRO_422 = _erro(422, "Dados inválidos. `detail` explica o motivo (texto) ou lista os campos com erro.")


def ok(modelo, codigo: int = 200, descricao: str = "Sucesso.") -> dict:
    """Resposta de sucesso documentada (a rota continua montando o JSON do jeito dela)."""
    return {codigo: {"model": modelo, "description": descricao}}
