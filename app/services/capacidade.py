"""Turnos do mês de um espaço, com as mesmas regras do front (src/lib/agenda.js):

- No calendário: turnos que abrem em cada dia do mês (dias × turnos da agenda).
- Não disponíveis: agendamentos do tipo bloqueio (ativos) em turnos que abrem naquele dia.
- Em aberto: no calendário − não disponíveis (capacidade prática).
- Ocupados: turnos locados (agendamentos de locação ativos).
Salas que cobram por hora contam horas em vez de turnos.
"""

import calendar
from datetime import date

from app import models as m
from app.models.enums import Modalidade, StatusAgenda, TipoAgendamento, TipoEspaco
from app.services.serializar import num


def _minutos(h: str) -> int:
    a, b = h.split(":")
    return int(a) * 60 + int(b)


def horas_de(chave: str) -> float:
    ini, fim = chave.split("-")
    return max(0, (_minutos(fim) - _minutos(ini)) / 60)


def dow_js(d: date) -> int:
    """Dia da semana como o getDay() do JavaScript: 0 = domingo."""
    return (d.weekday() + 1) % 7


def usa_agenda(e: m.Espaco) -> bool:
    return e.tipo != TipoEspaco.ADMINISTRATIVO and e.modalidade != Modalidade.MENSAL


async def turnos_de(e: m.Espaco) -> list[m.Turno]:
    if e.turnos_proprios:
        return await m.Turno.filter(espaco_id=e.id)
    return await m.Turno.filter(espaco_id__isnull=True)


async def capacidade_mes(e: m.Espaco, mes: str) -> dict:
    ano, mm = (int(x) for x in mes.split("-"))
    if not usa_agenda(e):
        return {"espacoId": e.id, "mes": mes, "usaAgenda": False, "capacidade": num(e.capacidade)}

    por_hora = e.modalidade == Modalidade.HORA
    turnos = await turnos_de(e)
    por_chave = {t.chave: t for t in turnos}
    unid = lambda chaves: sum(horas_de(k) for k in chaves) if por_hora else len(chaves)  # noqa: E731

    dias = [date(ano, mm, d) for d in range(1, calendar.monthrange(ano, mm)[1] + 1)]
    calendario = sum(unid([t.chave for t in turnos if dow_js(d) in t.dias]) for d in dias)

    ags = await m.Agendamento.filter(
        espaco_id=e.id, data__gte=dias[0], data__lte=dias[-1]
    ).exclude(status=StatusAgenda.CANCELADA)
    bloqueados = sum(
        unid([k for k in a.slots if k in por_chave and dow_js(a.data) in por_chave[k].dias])
        for a in ags
        if a.tipo == TipoAgendamento.BLOQUEIO
    )
    locacoes = [a for a in ags if a.tipo == TipoAgendamento.LOCACAO]
    ocupados = sum(unid(a.slots) for a in locacoes)
    em_aberto = calendario - bloqueados
    preco = float(e.preco_turno or e.preco or 0)
    return {
        "espacoId": e.id,
        "mes": mes,
        "usaAgenda": True,
        "unidade": "horas" if por_hora else "turnos",
        "noCalendario": num(calendario),
        "naoDisponiveis": num(bloqueados),
        "emAberto": num(em_aberto),
        "ocupados": num(ocupados),
        "livres": num(max(0, em_aberto - ocupados)),
        "ocupacao": round(ocupados / em_aberto, 4) if em_aberto else 0,
        "profissionais": len({a.profissional_id or a.cliente for a in locacoes if a.profissional_id or a.cliente}),
        "receitaLocada": num(sum(float(a.valor) for a in locacoes)),
        "receitaBloqueada": num(bloqueados * preco),
    }


async def conflitos(espaco_id: str, dia: date, slots: list[str], ignorar_id: str | None = None) -> list[str]:
    """Turnos que já estão ocupados ou indisponíveis nesse dia."""
    q = m.Agendamento.filter(espaco_id=espaco_id, data=dia).exclude(status=StatusAgenda.CANCELADA)
    if ignorar_id:
        q = q.exclude(id=ignorar_id)
    usados = {k for a in await q for k in a.slots}
    return sorted(set(slots) & usados)
