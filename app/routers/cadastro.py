"""Turnos da Santé, espaços (centros de custo), custos fixos e locatários."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query
from tortoise.transactions import in_transaction

from app import models as m
from app import schemas as s
from app.routers.comum import achar, validar_mes
from app.services import documento, gravar
from app.services import serializar as ser
from app.services.capacidade import capacidade_mes

router = APIRouter()


# ---------- clínica ----------
@router.get("/clinica", tags=["clínica"], summary="Dados da Santé e meta de ocupação")
async def ler_clinica():
    doc = await documento.exportar()
    if not doc:
        raise HTTPException(404, "Banco vazio. Importe um sante.json em PUT /api/dados.")
    return {"meta": doc["meta"], "metas": doc["metas"]}


@router.put("/clinica", tags=["clínica"])
async def salvar_clinica(dados: s.ClinicaDados):
    c = await m.Clinica.first()
    if c is None:
        raise HTTPException(404, "Banco vazio. Importe um sante.json em PUT /api/dados.")
    c.update_from_dict({
        "nome": dados.meta.clinica,
        "razao_social": dados.meta.razao_social,
        "endereco": dados.meta.endereco,
        "telefone": dados.meta.telefone,
        "whatsapp": dados.meta.whatsapp,
        "site": dados.meta.site,
        "instagram": dados.meta.instagram,
        "dados_atualizados_em": dados.meta.atualizado_em,
        "ocupacao_alvo": dados.metas.ocupacao_alvo,
    })
    await c.save()
    return await ler_clinica()


# ---------- turnos da Santé ----------
@router.get("/turnos", tags=["turnos"], summary="Turnos da Santé (usados pelas salas sem turnos próprios)")
async def ler_turnos():
    c = await m.Clinica.first()
    return ser.agenda(await m.Turno.filter(espaco_id__isnull=True), c.turnos_minimo if c else 1)


@router.put("/turnos", tags=["turnos"], summary="Substitui os turnos da Santé")
async def salvar_turnos(dados: s.Agenda):
    async with in_transaction():
        await gravar.gravar_turnos(dados.horarios)
        await m.Clinica.all().update(turnos_minimo=dados.minimo)
    return await ler_turnos()


# ---------- espaços ----------
async def _espaco_out(id: str) -> dict:
    e = await m.Espaco.get(id=id).prefetch_related("turnos", "despesas")
    return ser.espaco(e)


@router.get("/espacos", tags=["espaços"])
async def listar_espacos():
    return [ser.espaco(e) for e in await m.Espaco.all().prefetch_related("turnos", "despesas")]


@router.get("/espacos/{id}", tags=["espaços"])
async def ler_espaco(id: str):
    await achar(m.Espaco, id, "Espaço")
    return await _espaco_out(id)


@router.post("/espacos", tags=["espaços"], status_code=201)
async def criar_espaco(dados: s.Espaco):
    if dados.id and await m.Espaco.exists(id=dados.id):
        raise HTTPException(409, f"Já existe o espaço {dados.id}.")
    async with in_transaction():
        e = await gravar.gravar_espaco(dados, ordem=await m.Espaco.all().count())
    return await _espaco_out(e.id)


@router.put("/espacos/{id}", tags=["espaços"])
async def atualizar_espaco(id: str, dados: s.Espaco):
    await achar(m.Espaco, id, "Espaço")
    dados.id = id
    async with in_transaction():
        await gravar.gravar_espaco(dados)
    return await _espaco_out(id)


@router.delete("/espacos/{id}", tags=["espaços"], status_code=204)
async def excluir_espaco(id: str):
    e = await achar(m.Espaco, id, "Espaço")
    if await m.Contrato.exists(espaco_id=id):
        raise HTTPException(409, "Este espaço tem contratos. Exclua ou mova os contratos antes.")
    await e.delete()


@router.get("/espacos/{id}/capacidade", tags=["espaços"], summary="Turnos do mês: no calendário, não disponíveis, em aberto e ocupados")
async def capacidade(id: str, mes: str = Query(default_factory=lambda: date.today().strftime("%Y-%m"), examples=["2026-11"])):
    return await capacidade_mes(await achar(m.Espaco, id, "Espaço"), validar_mes(mes))


@router.get("/capacidade", tags=["espaços"], summary="Turnos do mês de todos os espaços")
async def capacidade_todos(mes: str = Query(default_factory=lambda: date.today().strftime("%Y-%m"))):
    mes = validar_mes(mes)
    return [await capacidade_mes(e, mes) for e in await m.Espaco.all()]


# ---------- custos ----------
@router.get("/custos", tags=["custos"])
async def ler_custos():
    c = await m.Clinica.first()
    return {
        "fixos": [ser.custo(x) for x in await m.CustoFixo.all()],
        "impostos": ser.num(c.impostos) if c else 0,
        "comissoes": ser.num(c.comissoes) if c else 0,
    }


@router.put("/custos", tags=["custos"])
async def salvar_custos(dados: s.Custos):
    async with in_transaction():
        await gravar.gravar_custos(dados)
    return await ler_custos()


# ---------- locatários ----------
async def _prof_out(id: str) -> dict:
    return ser.profissional(await m.Profissional.get(id=id).prefetch_related("links"))


@router.get("/profissionais", tags=["locatários"])
async def listar_profissionais():
    return [ser.profissional(p) for p in await m.Profissional.all().prefetch_related("links")]


@router.get("/profissionais/{id}", tags=["locatários"])
async def ler_profissional(id: str):
    await achar(m.Profissional, id, "Profissional")
    return await _prof_out(id)


async def _nome_livre(nome: str, id: str | None) -> None:
    q = m.Profissional.filter(nome__iexact=nome.strip())
    if id:
        q = q.exclude(id=id)
    if await q.exists():
        raise HTTPException(409, "Já existe um profissional com esse nome.")


@router.post("/profissionais", tags=["locatários"], status_code=201)
async def criar_profissional(dados: s.Profissional):
    await _nome_livre(dados.nome, None)
    async with in_transaction():
        p = await gravar.gravar_profissional(dados)
    return await _prof_out(p.id)


@router.put("/profissionais/{id}", tags=["locatários"])
async def atualizar_profissional(id: str, dados: s.Profissional):
    await achar(m.Profissional, id, "Profissional")
    await _nome_livre(dados.nome, id)
    dados.id = id
    async with in_transaction():
        await gravar.gravar_profissional(dados)
    return await _prof_out(id)


@router.delete("/profissionais/{id}", tags=["locatários"], status_code=204)
async def excluir_profissional(id: str):
    await (await achar(m.Profissional, id, "Profissional")).delete()
