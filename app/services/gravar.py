"""Grava os schemas da API no banco. Usado pelas rotas e pela importação do sante.json."""

from app import models as m
from app import schemas as s
from app.services.serializar import uid


async def gravar_turnos(turnos: list[s.Horario], espaco: m.Espaco | None = None) -> None:
    """Substitui os turnos da Santé (espaco=None) ou os turnos próprios de uma sala."""
    if espaco is None:
        await m.Turno.filter(espaco_id__isnull=True).delete()
    else:
        await m.Turno.filter(espaco_id=espaco.id).delete()
    await m.Turno.bulk_create(
        [
            m.Turno(espaco=espaco, nome=h.nome, ini=h.ini, fim=h.fim, dias=h.dias, ordem=i)
            for i, h in enumerate(turnos)
        ]
    )


async def gravar_espaco(dados: s.Espaco, ordem: int | None = None) -> m.Espaco:
    campos = {
        "nome": dados.nome.strip(),
        "tipo": dados.tipo,
        "modalidade": dados.modalidade,
        "capacidade": dados.capacidade,
        "preco": dados.preco,
        "preco_turno": dados.preco_turno,
        "descricao": dados.descricao,
        "obs": dados.obs,
        "turnos_proprios": dados.agenda is not None,
        "agenda_minimo": dados.agenda.minimo if dados.agenda else None,
    }
    if ordem is not None:
        campos["ordem"] = ordem
    e, _ = await m.Espaco.update_or_create(id=dados.id or uid("e"), defaults=campos)
    await m.DespesaEspaco.filter(espaco_id=e.id).delete()
    await m.DespesaEspaco.bulk_create(
        [m.DespesaEspaco(id=d.id or uid("d"), espaco=e, descricao=d.descricao, valor=d.valor) for d in dados.despesas]
    )
    if dados.agenda:
        await gravar_turnos(dados.agenda.horarios, e)
    else:
        await m.Turno.filter(espaco_id=e.id).delete()
    return e


async def gravar_profissional(dados: s.Profissional) -> m.Profissional:
    campos = dados.model_dump(exclude={"id", "redes", "outras"})
    campos["nome"] = campos["nome"].strip()
    p, _ = await m.Profissional.update_or_create(id=dados.id or uid("p"), defaults=campos)
    await m.ProfissionalLink.filter(profissional_id=p.id).delete()
    links = [m.ProfissionalLink(profissional=p, rede=k, valor=v.strip()) for k, v in dados.redes.items() if v.strip()]
    links += [m.ProfissionalLink(profissional=p, rede="outra", valor=o.url, rotulo=o.rotulo) for o in dados.outras if o.url]
    await m.ProfissionalLink.bulk_create(links)
    return p


async def gravar_campanha(dados: s.Campanha) -> m.Campanha:
    campos = dados.model_dump(exclude={"id", "espacos"})
    c, _ = await m.Campanha.update_or_create(id=dados.id or uid("k"), defaults=campos)
    await c.espacos.clear()
    if dados.espacos:
        await c.espacos.add(*await m.Espaco.filter(id__in=dados.espacos))
    return c


async def gravar_contrato(dados: s.Contrato) -> m.Contrato:
    campos = dados.model_dump(exclude={"id", "campanha"})
    campos["campanha_id"] = dados.campanha if dados.campanha and await m.Campanha.exists(id=dados.campanha) else None
    c, _ = await m.Contrato.update_or_create(id=dados.id or uid("ct"), defaults=campos)
    return c


async def gravar_agendamento(dados: s.Agendamento) -> m.Agendamento:
    campos = dados.model_dump(exclude={"id"})
    a, _ = await m.Agendamento.update_or_create(id=dados.id or uid("ag"), defaults=campos)
    return a


async def gravar_custos(dados: s.Custos) -> None:
    clinica = await m.Clinica.first()
    if clinica:
        clinica.impostos = dados.impostos
        clinica.comissoes = dados.comissoes
        await clinica.save()
    await m.CustoFixo.all().delete()
    await m.CustoFixo.bulk_create(
        [m.CustoFixo(id=c.id or uid("c"), descricao=c.descricao, valor=c.valor, ordem=i) for i, c in enumerate(dados.fixos)]
    )
