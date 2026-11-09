"""Valores fixos usados pelo front (src/lib/calc.js e src/lib/agenda.js)."""

from enum import StrEnum


class Modalidade(StrEnum):
    HORA = "Hora"
    TURNO = "Turno"
    MENSAL = "Mensal"


class TipoEspaco(StrEnum):
    CONSULTORIO = "Consultório"
    PISCINA = "Piscina"
    ADMINISTRATIVO = "Administrativo"
    PROCEDIMENTOS = "Sala de procedimentos"
    OUTRO = "Outro"


class StatusContrato(StrEnum):
    CONFIRMADA = "Confirmada"
    PROPOSTA = "Proposta"
    BASE_INICIAL = "Base inicial"
    CANCELADA = "Cancelada"


class StatusAgenda(StrEnum):
    CONFIRMADA = "Confirmada"
    PROPOSTA = "Proposta"
    CANCELADA = "Cancelada"


class TipoAgendamento(StrEnum):
    LOCACAO = "locacao"  # turno locado a um profissional
    BLOQUEIO = "bloqueio"  # turno "Não disponível": sai da capacidade do mês


class StatusCampanha(StrEnum):
    PLANEJADA = "Planejada"
    ATIVA = "Ativa"
    PAUSADA = "Pausada"
    CONCLUIDA = "Concluída"
