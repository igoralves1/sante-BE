"""Saúde da API e o documento inteiro nos formatos de arquivo do front."""

from typing import Any

from fastapi import APIRouter, Body, HTTPException
from tortoise import connections

from app import schemas as s
from app.routers.comum import ERRO_404, ERRO_422, ok
from app.services import documento

router = APIRouter()


@router.get("/saude", tags=["sistema"], summary="A API e o banco estão no ar?", responses=ok(s.Saude))
async def saude():
    """Faz um `SELECT 1` no banco. Usado pelo healthcheck do Docker."""
    await connections.get("default").execute_query("SELECT 1")
    return {"status": "ok", "banco": "ok"}


@router.get(
    "/dados", tags=["documento"], summary="Tudo no formato do sante.json",
    responses={**ok(s.DocumentoSaida), **ERRO_404},
)
async def exportar():
    """O sistema inteiro num documento só: clínica, metas, turnos, espaços, custos, campanhas,
    contratos, agendamentos e locatários.

    É a primeira chamada do front. Também serve de backup: salve a resposta como `sante.json`."""
    doc = await documento.exportar()
    if not doc:
        raise HTTPException(404, "Banco vazio. Importe um sante.json em PUT /api/dados.")
    return doc


@router.put(
    "/dados", tags=["documento"], summary="Substitui tudo por um sante.json (tudo ou nada)",
    responses={**ok(s.Importado), **ERRO_422},
)
async def importar(doc: s.Documento):
    """**Apaga todos os dados de cadastro e operação** e grava os do documento, numa transação só.
    Se algo falhar, nada muda.

    Usado em **Base de dados** para importar uma planilha ou um arquivo, ou para restaurar a versão
    publicada. Os dados de mercado (`/api/mercado/*`) não são tocados."""
    return {"importado": await documento.importar(doc)}


MERCADO = Body(
    ...,
    description="Documento no formato do arquivo do front (`src/data/concorrentes.json` ou `src/data/social.json`).",
)


@router.get(
    "/mercado/concorrentes", tags=["mercado"], summary="Coleta de concorrentes",
    responses=ok(dict[str, Any], descricao="Documento no formato de `concorrentes.json`."),
)
async def concorrentes():
    """Concorrentes de Maceió (preços, horários, diferenciais, Instagram, Google), buscas no
    Google Maps, notas de PageSpeed e tráfego dos sites. Dados de páginas públicas, coletados à mão."""
    return await documento.exportar_concorrentes()


@router.put(
    "/mercado/concorrentes", tags=["mercado"], summary="Substitui a coleta de concorrentes",
    responses=ok(dict[str, Any], descricao="A coleta como ficou gravada."),
)
async def importar_concorrentes(doc: dict[str, Any] = MERCADO):
    """Troca toda a coleta de concorrentes pela do documento, numa transação só."""
    await documento.importar_concorrentes(doc)
    return await documento.exportar_concorrentes()


@router.get(
    "/mercado/social", tags=["mercado"], summary="Monitor social",
    responses=ok(dict[str, Any], descricao="Documento no formato de `social.json`."),
)
async def social():
    """Redes sociais acompanhadas, perfis da Santé e dos concorrentes em cada rede (seguidores,
    publicações) e os últimos posts. Dados de páginas públicas, coletados à mão."""
    return await documento.exportar_social()


@router.put(
    "/mercado/social", tags=["mercado"], summary="Substitui o monitor social",
    responses=ok(dict[str, Any], descricao="O monitor como ficou gravado."),
)
async def importar_social(doc: dict[str, Any] = MERCADO):
    """Troca todo o monitor social pelo do documento, numa transação só."""
    await documento.importar_social(doc)
    return await documento.exportar_social()
