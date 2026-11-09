"""Converte linhas do banco para o formato JSON do front (camelCase, igual ao sante.json)."""

import secrets
from datetime import date
from decimal import Decimal

from app import models as m


def uid(prefixo: str) -> str:
    return f"{prefixo}{secrets.token_hex(4)}"


def num(v: Decimal | float | int | None) -> float | int | None:
    if v is None:
        return None
    f = float(v)
    return int(f) if f.is_integer() else f


def iso(d: date | None) -> str:
    return d.isoformat() if d else ""


def horario(t: m.Turno) -> dict:
    return {"nome": t.nome, "ini": t.ini, "fim": t.fim, "dias": list(t.dias)}


def agenda(turnos: list[m.Turno], minimo: int) -> dict:
    return {"versao": 3, "minimo": minimo, "horarios": [horario(t) for t in turnos]}


def espaco(e: m.Espaco) -> dict:
    """Espera `turnos` e `despesas` já carregados (prefetch_related)."""
    return {
        "id": e.id,
        "nome": e.nome,
        "tipo": e.tipo.value,
        "modalidade": e.modalidade.value,
        "capacidade": num(e.capacidade),
        "preco": num(e.preco),
        "precoTurno": num(e.preco_turno),
        "descricao": e.descricao,
        "obs": e.obs,
        "despesas": [{"id": d.id, "descricao": d.descricao, "valor": num(d.valor)} for d in e.despesas],
        "agenda": agenda(list(e.turnos), e.agenda_minimo or 1) if e.turnos_proprios else None,
    }


def contrato(c: m.Contrato) -> dict:
    return {
        "id": c.id,
        "espacoId": c.espaco_id,
        "profissionalId": c.profissional_id or "",
        "cliente": c.cliente,
        "modalidade": c.modalidade.value,
        "quantidade": num(c.quantidade),
        "preco": num(c.preco),
        "inicio": iso(c.inicio),
        "fim": iso(c.fim),
        "status": c.status.value,
        "campanha": c.campanha_id or "",
        "obs": c.obs,
    }


def agendamento(a: m.Agendamento) -> dict:
    return {
        "id": a.id,
        "tipo": a.tipo.value,
        "espacoId": a.espaco_id,
        "data": iso(a.data),
        "slots": list(a.slots),
        "profissionalId": a.profissional_id or "",
        "cliente": a.cliente,
        "valor": num(a.valor),
        "status": a.status.value,
        "obs": a.obs,
        "grupo": a.grupo,
    }


def profissional(p: m.Profissional) -> dict:
    """Espera `links` já carregados."""
    links = list(p.links)
    return {
        "id": p.id,
        "nome": p.nome,
        "profissao": p.profissao,
        "especialidade": p.especialidade,
        "registro": p.registro,
        "anoFormatura": p.ano_formatura or "",
        "telefone": p.telefone,
        "email": p.email,
        "canal": p.canal,
        "redes": {l.rede: l.valor for l in links if l.rede != "outra"},
        "outras": [{"rotulo": l.rotulo, "url": l.valor} for l in links if l.rede == "outra"],
        "obs": p.obs,
        "criadoEm": p.criado_em.date().isoformat() if p.criado_em else "",
    }


def campanha(c: m.Campanha) -> dict:
    """Espera `espacos` já carregados."""
    return {
        "id": c.id,
        "nome": c.nome,
        "canal": c.canal,
        "espacos": [e.id for e in c.espacos],
        "inicio": iso(c.inicio),
        "fim": iso(c.fim),
        "orcamento": num(c.orcamento),
        "leads": c.leads,
        "visitas": c.visitas,
        "status": c.status.value,
        "obs": c.obs,
    }


def custo(c: m.CustoFixo) -> dict:
    return {"id": c.id, "descricao": c.descricao, "valor": num(c.valor)}
