"""Carteira de contratos, agenda de turnos e campanhas."""

from fastapi import APIRouter, HTTPException, Path, Query
from tortoise.transactions import in_transaction

from app import models as m
from app import schemas as s
from app.models.enums import TipoAgendamento
from app.routers.comum import ERRO_404, ERRO_409, ERRO_422, achar, ok, validar_mes
from app.services import gravar
from app.services import serializar as ser
from app.services.capacidade import conflitos, dow_js, turnos_de, usa_agenda

router = APIRouter()

ESPACO_FILTRO = Query(None, description="Só deste espaço (ID).", examples=["e1"])


# ---------- contratos ----------
@router.get("/contratos", tags=["contratos"], summary="Lista os contratos", responses=ok(list[s.ContratoSaida]))
async def listar_contratos(espaco: str | None = ESPACO_FILTRO):
    """Carteira de contratos (locações recorrentes), por data de início."""
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


@router.post(
    "/contratos", tags=["contratos"], status_code=201, summary="Cria um contrato",
    responses={**ok(s.ContratoSaida, 201, "Contrato criado."), **ERRO_404, **ERRO_422},
)
async def criar_contrato(dados: s.Contrato):
    """Cria um contrato. O espaço e o locatário precisam existir (404).
    O término não pode ser antes do início (422)."""
    await _validar_contrato(dados)
    return ser.contrato(await gravar.gravar_contrato(dados))


@router.put(
    "/contratos/{id}", tags=["contratos"], summary="Atualiza um contrato",
    responses={**ok(s.ContratoSaida), **ERRO_404, **ERRO_422},
)
async def atualizar_contrato(dados: s.Contrato, id: str = Path(description="ID do contrato.", examples=["ct1"])):
    """Substitui o contrato inteiro."""
    await achar(m.Contrato, id, "Contrato")
    await _validar_contrato(dados)
    dados.id = id
    return ser.contrato(await gravar.gravar_contrato(dados))


@router.delete("/contratos/{id}", tags=["contratos"], status_code=204, summary="Exclui um contrato", responses=ERRO_404)
async def excluir_contrato(id: str = Path(description="ID do contrato.", examples=["ct1"])):
    """Exclui o contrato."""
    await (await achar(m.Contrato, id, "Contrato")).delete()


# ---------- agenda ----------
@router.get(
    "/agendamentos", tags=["agenda"], summary="Lista os agendamentos",
    responses={**ok(list[s.AgendamentoSaida]), **ERRO_422},
)
async def listar_agendamentos(
    espaco: str | None = ESPACO_FILTRO,
    mes: str | None = Query(None, description="Só deste mês, AAAA-MM.", examples=["2026-11"]),
):
    """Locações e bloqueios ("Não disponível") da agenda, por data."""
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


REGRAS_AGENDA = """

Regras:

- o espaço precisa usar agenda: espaços `Mensal` e `Administrativo` são recusados (422);
- cada turno de `slots` precisa abrir nesse dia da semana, nos turnos do espaço ou da Santé (422);
- uma locação precisa de `profissionalId` ou `cliente` (422);
- um turno não pode estar locado ou bloqueado duas vezes no mesmo dia (409);
- num bloqueio, `profissionalId`, `cliente` e `valor` são zerados."""


@router.post(
    "/agendamentos", tags=["agenda"], status_code=201, summary="Cria um agendamento",
    description="Loca turnos de um dia a um profissional (`locacao`) ou marca como não disponível (`bloqueio`)." + REGRAS_AGENDA,
    responses={**ok(s.AgendamentoSaida, 201, "Agendamento criado."), **ERRO_404, **ERRO_409, **ERRO_422},
)
async def criar_agendamento(dados: s.Agendamento):
    await _validar_agendamento(dados)
    return ser.agendamento(await gravar.gravar_agendamento(dados))


@router.post(
    "/agendamentos/lote", tags=["agenda"], status_code=201, summary="Cria vários agendamentos (tudo ou nada)",
    description=(
        "Usado ao repetir uma locação ou um bloqueio no mês ou no ano. Se um item falhar, nenhum é gravado.\n\n"
        "Cada item mantém o `grupo` que veio. Se nenhum item tiver grupo, todos recebem o mesmo grupo novo, "
        "para poderem ser excluídos juntos em `DELETE /api/agendamentos/grupo/{grupo}`." + REGRAS_AGENDA
    ),
    responses={**ok(list[s.AgendamentoSaida], 201, "Agendamentos criados."), **ERRO_404, **ERRO_409, **ERRO_422},
)
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



@router.put(
    "/agendamentos/{id}", tags=["agenda"], summary="Atualiza um agendamento",
    description="Substitui o agendamento inteiro." + REGRAS_AGENDA,
    responses={**ok(s.AgendamentoSaida), **ERRO_404, **ERRO_409, **ERRO_422},
)
async def atualizar_agendamento(dados: s.Agendamento, id: str = Path(description="ID do agendamento.", examples=["ag1"])):
    await achar(m.Agendamento, id, "Agendamento")
    dados.id = id
    await _validar_agendamento(dados, ignorar_id=id)
    return ser.agendamento(await gravar.gravar_agendamento(dados))


@router.delete("/agendamentos/{id}", tags=["agenda"], status_code=204, summary="Exclui um agendamento", responses=ERRO_404)
async def excluir_agendamento(id: str = Path(description="ID do agendamento.", examples=["ag1"])):
    """Exclui um dia da agenda. Os outros dias da mesma repetição continuam."""
    await (await achar(m.Agendamento, id, "Agendamento")).delete()


@router.delete(
    "/agendamentos/grupo/{grupo}", tags=["agenda"], summary="Exclui todos os dias de uma repetição",
    responses=ok(s.Excluidos),
)
async def excluir_grupo(grupo: str = Path(description="Valor de `grupo` dos agendamentos.", examples=["g1a2b3c4d"])):
    """Exclui todos os agendamentos com este `grupo` e diz quantos foram."""
    return {"excluidos": await m.Agendamento.filter(grupo=grupo).delete()}


# ---------- campanhas ----------
async def _campanha_out(id: str) -> dict:
    return ser.campanha(await m.Campanha.get(id=id).prefetch_related("espacos"))


ID_CAMPANHA = Path(description="ID da campanha.", examples=["cp1"])


@router.get("/campanhas", tags=["campanhas"], summary="Lista as campanhas", responses=ok(list[s.CampanhaSaida]))
async def listar_campanhas():
    """Ações comerciais, com os espaços divulgados e os resultados (leads e visitas)."""
    return [ser.campanha(c) for c in await m.Campanha.all().prefetch_related("espacos")]


@router.post(
    "/campanhas", tags=["campanhas"], status_code=201, summary="Cria uma campanha",
    responses={**ok(s.CampanhaSaida, 201, "Campanha criada."), **ERRO_422},
)
async def criar_campanha(dados: s.Campanha):
    """Cria uma campanha. IDs de espaços que não existem são ignorados."""
    async with in_transaction():
        c = await gravar.gravar_campanha(dados)
    return await _campanha_out(c.id)


@router.put(
    "/campanhas/{id}", tags=["campanhas"], summary="Atualiza uma campanha",
    responses={**ok(s.CampanhaSaida), **ERRO_404, **ERRO_422},
)
async def atualizar_campanha(dados: s.Campanha, id: str = ID_CAMPANHA):
    """Substitui a campanha inteira, incluindo a lista de espaços."""
    await achar(m.Campanha, id, "Campanha")
    dados.id = id
    async with in_transaction():
        await gravar.gravar_campanha(dados)
    return await _campanha_out(id)


@router.delete("/campanhas/{id}", tags=["campanhas"], status_code=204, summary="Exclui uma campanha", responses=ERRO_404)
async def excluir_campanha(id: str = ID_CAMPANHA):
    """Exclui a campanha. Contratos ligados a ela continuam, sem o vínculo."""
    await (await achar(m.Campanha, id, "Campanha")).delete()
