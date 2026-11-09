"""Carteira de contratos, agenda de turnos e campanhas."""

from fastapi import APIRouter, HTTPException
from tortoise.transactions import in_transaction

from app import models as m
from app import schemas as s
from app.models.enums import TipoAgendamento
from app.routers.comum import achar, validar_mes
from app.services import gravar
from app.services import serializar as ser
from app.services.capacidade import conflitos, dow_js, turnos_de, usa_agenda

router = APIRouter()


# ---------- contratos ----------
@router.get("/contratos", tags=["contratos"])
async def listar_contratos(espaco: str | None = None):
    q = m.Contrato.all().order_by("inicio", "id")
    if espaco:
        q = q.filter(espaco_id=espaco)
    return [ser.contrato(c) for c in await q]


async def _validar_contrato(d: s.Contrato) -> None:
    await achar(m.Espaco, d.espaco_id, "Espaço")
    if d.profissional_id:
        await achar(m.Profissional, d.profissional_id, "Profissional")
    if d.fim and d.fim < d.inicio:
        raise HTTPException(422, "O término não pode ser antes do início.")


@router.post("/contratos", tags=["contratos"], status_code=201)
async def criar_contrato(dados: s.Contrato):
    await _validar_contrato(dados)
    return ser.contrato(await gravar.gravar_contrato(dados))


@router.put("/contratos/{id}", tags=["contratos"])
async def atualizar_contrato(id: str, dados: s.Contrato):
    await achar(m.Contrato, id, "Contrato")
    await _validar_contrato(dados)
    dados.id = id
    return ser.contrato(await gravar.gravar_contrato(dados))


@router.delete("/contratos/{id}", tags=["contratos"], status_code=204)
async def excluir_contrato(id: str):
    await (await achar(m.Contrato, id, "Contrato")).delete()


# ---------- agenda ----------
@router.get("/agendamentos", tags=["agenda"])
async def listar_agendamentos(espaco: str | None = None, mes: str | None = None):
    q = m.Agendamento.all().order_by("data", "id")
    if espaco:
        q = q.filter(espaco_id=espaco)
    if mes:
        ano, mm = (int(x) for x in validar_mes(mes).split("-"))
        q = q.filter(data__year=ano, data__month=mm)
    return [ser.agendamento(a) for a in await q]


async def _validar_agendamento(d: s.Agendamento, ignorar_id: str | None = None) -> None:
    e = await achar(m.Espaco, d.espaco_id, "Espaço")
    if not usa_agenda(e):
        raise HTTPException(422, f"O espaço {e.nome} é locado por mês e não usa agenda de turnos.")
    abertos = {t.chave for t in await turnos_de(e) if dow_js(d.data) in t.dias}
    fora = [k for k in d.slots if k not in abertos]
    if fora:
        raise HTTPException(422, f"{e.nome} não abre {', '.join(fora)} em {d.data.isoformat()}.")
    if d.tipo == TipoAgendamento.LOCACAO and not (d.profissional_id or d.cliente):
        raise HTTPException(422, "Escolha o profissional da locação.")
    if d.profissional_id:
        p = await achar(m.Profissional, d.profissional_id, "Profissional")
        d.cliente = d.cliente or p.nome
    if d.tipo == TipoAgendamento.BLOQUEIO:
        d.profissional_id, d.cliente, d.valor = None, "", 0
    usados = await conflitos(d.espaco_id, d.data, d.slots, ignorar_id)
    if usados:
        raise HTTPException(409, f"Turno já ocupado em {d.data.isoformat()}: {', '.join(usados)}.")


@router.post("/agendamentos", tags=["agenda"], status_code=201)
async def criar_agendamento(dados: s.Agendamento):
    await _validar_agendamento(dados)
    return ser.agendamento(await gravar.gravar_agendamento(dados))


@router.post("/agendamentos/lote", tags=["agenda"], status_code=201, summary="Vários agendamentos de uma vez (repetir no mês ou no ano); tudo ou nada")
async def criar_lote(itens: list[s.Agendamento]):
    if not itens:
        raise HTTPException(422, "Envie pelo menos um agendamento.")
    # cada item mantém o grupo que veio; sem grupo nenhum, os itens viram uma repetição só
    novo = ser.uid("g") if len(itens) > 1 and not any(d.grupo for d in itens) else ""
    async with in_transaction():
        criados = []
        for d in itens:
            d.grupo = d.grupo or novo
            await _validar_agendamento(d)
            criados.append(ser.agendamento(await gravar.gravar_agendamento(d)))
    return criados


@router.put("/agendamentos/{id}", tags=["agenda"])
async def atualizar_agendamento(id: str, dados: s.Agendamento):
    await achar(m.Agendamento, id, "Agendamento")
    dados.id = id
    await _validar_agendamento(dados, ignorar_id=id)
    return ser.agendamento(await gravar.gravar_agendamento(dados))


@router.delete("/agendamentos/{id}", tags=["agenda"], status_code=204)
async def excluir_agendamento(id: str):
    await (await achar(m.Agendamento, id, "Agendamento")).delete()


@router.delete("/agendamentos/grupo/{grupo}", tags=["agenda"], summary="Exclui todos os dias de uma repetição")
async def excluir_grupo(grupo: str):
    return {"excluidos": await m.Agendamento.filter(grupo=grupo).delete()}


# ---------- campanhas ----------
async def _campanha_out(id: str) -> dict:
    return ser.campanha(await m.Campanha.get(id=id).prefetch_related("espacos"))


@router.get("/campanhas", tags=["campanhas"])
async def listar_campanhas():
    return [ser.campanha(c) for c in await m.Campanha.all().prefetch_related("espacos")]


@router.post("/campanhas", tags=["campanhas"], status_code=201)
async def criar_campanha(dados: s.Campanha):
    async with in_transaction():
        c = await gravar.gravar_campanha(dados)
    return await _campanha_out(c.id)


@router.put("/campanhas/{id}", tags=["campanhas"])
async def atualizar_campanha(id: str, dados: s.Campanha):
    await achar(m.Campanha, id, "Campanha")
    dados.id = id
    async with in_transaction():
        await gravar.gravar_campanha(dados)
    return await _campanha_out(id)


@router.delete("/campanhas/{id}", tags=["campanhas"], status_code=204)
async def excluir_campanha(id: str):
    await (await achar(m.Campanha, id, "Campanha")).delete()
