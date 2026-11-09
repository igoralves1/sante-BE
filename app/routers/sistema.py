"""Saúde da API e o documento inteiro nos formatos de arquivo do front."""

from fastapi import APIRouter, Body, HTTPException
from tortoise import connections

from app import schemas as s
from app.services import documento

router = APIRouter()


@router.get("/saude", tags=["sistema"], summary="A API e o banco estão no ar?")
async def saude():
    await connections.get("default").execute_query("SELECT 1")
    return {"status": "ok", "banco": "ok"}


@router.get("/dados", tags=["documento"], summary="Tudo no formato do sante.json")
async def exportar():
    doc = await documento.exportar()
    if not doc:
        raise HTTPException(404, "Banco vazio. Importe um sante.json em PUT /api/dados.")
    return doc


@router.put("/dados", tags=["documento"], summary="Substitui tudo por um sante.json (tudo ou nada)")
async def importar(doc: s.Documento):
    return {"importado": await documento.importar(doc)}


@router.get("/mercado/concorrentes", tags=["mercado"], summary="Coleta de concorrentes (formato concorrentes.json)")
async def concorrentes():
    return await documento.exportar_concorrentes()


@router.put("/mercado/concorrentes", tags=["mercado"])
async def importar_concorrentes(doc: dict = Body(...)):
    await documento.importar_concorrentes(doc)
    return await documento.exportar_concorrentes()


@router.get("/mercado/social", tags=["mercado"], summary="Monitor social (formato social.json)")
async def social():
    return await documento.exportar_social()


@router.put("/mercado/social", tags=["mercado"])
async def importar_social(doc: dict = Body(...)):
    await documento.importar_social(doc)
    return await documento.exportar_social()
