"""Clínica, turnos da Santé, espaços (centros de custo), custos fixos e locatários."""

from datetime import date

from fastapi import APIRouter, HTTPException, Path, Query
from tortoise.transactions import in_transaction

from app import models as m
from app import schemas as s
from app.routers.comum import ERRO_404, ERRO_409, ERRO_422, achar, ok, validar_mes
from app.services import documento, gravar
from app.services import serializar as ser
from app.services.capacidade import capacidade_mes

router = APIRouter()

ID_ESPACO = Path(description="ID do espaço.", examples=["e1"])
ID_PROF = Path(description="ID do locatário.", examples=["p1"])


def _mes_atual() -> str:
    return date.today().strftime("%Y-%m")


MES = Query(default_factory=_mes_atual, description="Mês, AAAA-MM. Padrão: o mês atual.", examples=["2026-11"])


# ---------- clínica ----------
@router.get("/clinica", tags=["clínica"], summary="Dados da Santé e meta de ocupação", responses={**ok(s.ClinicaDados), **ERRO_404})
async def ler_clinica():
    """Nome, razão social, contatos, site, Instagram e a meta de ocupação (`metas.ocupacaoAlvo`)."""
    doc = await documento.exportar()
    if not doc:
        raise HTTPException(404, "Banco vazio. Importe um sante.json em PUT /api/dados.")
    return {"meta": doc["meta"], "metas": doc["metas"]}


@router.put(
    "/clinica", tags=["clínica"], summary="Atualiza os dados da Santé e a meta de ocupação",
    responses={**ok(s.ClinicaDados), **ERRO_404, **ERRO_422},
)
async def salvar_clinica(dados: s.ClinicaDados):
    """Substitui `meta` e `metas`. Devolve os dados como ficaram."""
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
@router.get("/turnos", tags=["turnos"], summary="Turnos da Santé", responses=ok(s.Agenda))
async def ler_turnos():
    """Turnos usados por todas as salas que não têm turnos próprios (`agenda: null`)."""
    c = await m.Clinica.first()
    return ser.agenda(await m.Turno.filter(espaco_id__isnull=True), c.turnos_minimo if c else 1)


@router.put("/turnos", tags=["turnos"], summary="Substitui os turnos da Santé", responses={**ok(s.Agenda), **ERRO_422})
async def salvar_turnos(dados: s.Agenda):
    """Troca todos os turnos da Santé. Vale na hora para todas as salas sem turnos próprios.

    Recusa (422) turnos com início depois do fim e turnos que se sobrepõem no mesmo dia.
    Agendamentos já gravados não mudam."""
    async with in_transaction():
        await gravar.gravar_turnos(dados.horarios)
        await m.Clinica.all().update(turnos_minimo=dados.minimo)
    return await ler_turnos()


# ---------- espaços ----------
async def _espaco_out(id: str) -> dict:
    e = await m.Espaco.get(id=id).prefetch_related("turnos", "despesas")
    return ser.espaco(e)


@router.get("/espacos", tags=["espaços"], summary="Lista os espaços", responses=ok(list[s.EspacoSaida]))
async def listar_espacos():
    """Todos os espaços (salas, piscina, áreas), na ordem da tela, com despesas e turnos próprios."""
    return [ser.espaco(e) for e in await m.Espaco.all().prefetch_related("turnos", "despesas")]


@router.get("/espacos/{id}", tags=["espaços"], summary="Um espaço", responses={**ok(s.EspacoSaida), **ERRO_404})
async def ler_espaco(id: str = ID_ESPACO):
    """Um espaço, com despesas e turnos próprios."""
    await achar(m.Espaco, id, "Espaço")
    return await _espaco_out(id)


@router.post(
    "/espacos", tags=["espaços"], status_code=201, summary="Cria um espaço",
    responses={**ok(s.EspacoSaida, 201, "Espaço criado."), **ERRO_409, **ERRO_422},
)
async def criar_espaco(dados: s.Espaco):
    """Cria o espaço no fim da lista. Sem `id`, a API gera um. Recusa nome ou ID repetido (409)."""
    if dados.id and await m.Espaco.exists(id=dados.id):
        raise HTTPException(409, f"Já existe o espaço {dados.id}.")
    async with in_transaction():
        e = await gravar.gravar_espaco(dados, ordem=await m.Espaco.all().count())
    return await _espaco_out(e.id)


@router.put(
    "/espacos/{id}", tags=["espaços"], summary="Atualiza um espaço",
    responses={**ok(s.EspacoSaida), **ERRO_404, **ERRO_409, **ERRO_422},
)
async def atualizar_espaco(dados: s.Espaco, id: str = ID_ESPACO):
    """Substitui o espaço inteiro, incluindo despesas e turnos próprios. `agenda: null` volta a usar os turnos da Santé."""
    await achar(m.Espaco, id, "Espaço")
    dados.id = id
    async with in_transaction():
        await gravar.gravar_espaco(dados)
    return await _espaco_out(id)


@router.delete(
    "/espacos/{id}", tags=["espaços"], status_code=204, summary="Exclui um espaço",
    responses={**ERRO_404, **ERRO_409},
)
async def excluir_espaco(id: str = ID_ESPACO):
    """Exclui o espaço com suas despesas, turnos próprios e agenda.
    Recusa (409) se o espaço ainda tem contratos."""
    e = await achar(m.Espaco, id, "Espaço")
    if await m.Contrato.exists(espaco_id=id):
        raise HTTPException(409, "Este espaço tem contratos. Exclua ou mova os contratos antes.")
    await e.delete()


@router.get(
    "/espacos/{id}/capacidade", tags=["espaços"], summary="Capacidade e ocupação de um espaço no mês",
    responses={**ok(s.Capacidade), **ERRO_404, **ERRO_422},
)
async def capacidade(id: str = ID_ESPACO, mes: str = MES):
    """Conta os turnos que abrem em cada dia do mês (no calendário), tira os "Não disponível"
    (em aberto) e compara com os locados (ocupados).

    Espaços cobrados por hora contam horas. Espaços `Mensal` e `Administrativo` não usam agenda
    e voltam com `usaAgenda: false`."""
    return await capacidade_mes(await achar(m.Espaco, id, "Espaço"), validar_mes(mes))


@router.get(
    "/capacidade", tags=["espaços"], summary="Capacidade e ocupação de todos os espaços no mês",
    responses={**ok(list[s.Capacidade]), **ERRO_422},
)
async def capacidade_todos(mes: str = MES):
    """O mesmo de `/espacos/{id}/capacidade`, para cada espaço."""
    mes = validar_mes(mes)
    return [await capacidade_mes(e, mes) for e in await m.Espaco.all()]


# ---------- custos ----------
@router.get("/custos", tags=["custos"], summary="Custos fixos, impostos e comissões", responses=ok(s.CustosSaida))
async def ler_custos():
    """Custos fixos mensais da casa e os percentuais de impostos e comissões sobre a receita."""
    c = await m.Clinica.first()
    return {
        "fixos": [ser.custo(x) for x in await m.CustoFixo.all()],
        "impostos": ser.num(c.impostos) if c else 0,
        "comissoes": ser.num(c.comissoes) if c else 0,
    }


@router.put("/custos", tags=["custos"], summary="Substitui os custos", responses={**ok(s.CustosSaida), **ERRO_422})
async def salvar_custos(dados: s.Custos):
    """Troca a lista de custos fixos e os percentuais. Custos fixos que não vierem são excluídos."""
    async with in_transaction():
        await gravar.gravar_custos(dados)
    return await ler_custos()


# ---------- locatários ----------
async def _prof_out(id: str) -> dict:
    return ser.profissional(await m.Profissional.get(id=id).prefetch_related("links"))


@router.get("/profissionais", tags=["locatários"], summary="Lista os locatários", responses=ok(list[s.ProfissionalSaida]))
async def listar_profissionais():
    """Todos os locatários, com redes sociais e links. Contém dados pessoais (LGPD)."""
    return [ser.profissional(p) for p in await m.Profissional.all().prefetch_related("links")]


@router.get("/profissionais/{id}", tags=["locatários"], summary="Um locatário", responses={**ok(s.ProfissionalSaida), **ERRO_404})
async def ler_profissional(id: str = ID_PROF):
    """Um locatário, com redes sociais e links."""
    await achar(m.Profissional, id, "Profissional")
    return await _prof_out(id)


async def _nome_livre(nome: str, id: str | None) -> None:
    q = m.Profissional.filter(nome__iexact=nome.strip())
    if id:
        q = q.exclude(id=id)
    if await q.exists():
        raise HTTPException(409, "Já existe um profissional com esse nome.")


@router.post(
    "/profissionais", tags=["locatários"], status_code=201, summary="Cadastra um locatário",
    responses={**ok(s.ProfissionalSaida, 201, "Locatário cadastrado."), **ERRO_409, **ERRO_422},
)
async def criar_profissional(dados: s.Profissional):
    """Cadastra um locatário. Recusa (409) um nome que já existe, sem diferenciar maiúsculas."""
    await _nome_livre(dados.nome, None)
    async with in_transaction():
        p = await gravar.gravar_profissional(dados)
    return await _prof_out(p.id)


@router.put(
    "/profissionais/{id}", tags=["locatários"], summary="Atualiza um locatário",
    responses={**ok(s.ProfissionalSaida), **ERRO_404, **ERRO_409, **ERRO_422},
)
async def atualizar_profissional(dados: s.Profissional, id: str = ID_PROF):
    """Substitui o cadastro inteiro, incluindo redes e links."""
    await achar(m.Profissional, id, "Profissional")
    await _nome_livre(dados.nome, id)
    dados.id = id
    async with in_transaction():
        await gravar.gravar_profissional(dados)
    return await _prof_out(id)


@router.delete(
    "/profissionais/{id}", tags=["locatários"], status_code=204, summary="Exclui um locatário",
    responses=ERRO_404,
)
async def excluir_profissional(id: str = ID_PROF):
    """Exclui o locatário e seus links. Contratos e agendamentos dele continuam, sem o vínculo
    (`profissionalId` fica vazio)."""
    await (await achar(m.Profissional, id, "Profissional")).delete()
