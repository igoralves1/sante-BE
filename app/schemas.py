"""Schemas da API. Os campos usam camelCase, no mesmo formato do sante.json do front."""

import re
from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from app.models.enums import (
    Modalidade,
    StatusAgenda,
    StatusCampanha,
    StatusContrato,
    TipoAgendamento,
    TipoEspaco,
)


def _vazio_para_none(v: Any) -> Any:
    return None if v == "" else v


# o front usa "" para "sem valor"; aqui vira None
Opcional = BeforeValidator(_vazio_para_none)
DataOpcional = Annotated[date | None, Opcional]
TextoOpcional = Annotated[str | None, Opcional]
NumeroOpcional = Annotated[float | None, Opcional]
InteiroOpcional = Annotated[int | None, Opcional]

HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
SLOT = re.compile(r"^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$")


class Schema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


# ---------- turnos ----------
class Horario(Schema):
    nome: str = Field(min_length=1, max_length=30)
    ini: str
    fim: str
    dias: list[int] = Field(min_length=1, description="0 = domingo ... 6 = sábado")

    @model_validator(mode="after")
    def validar(self):
        if not HORA.match(self.ini) or not HORA.match(self.fim):
            raise ValueError("Use o formato HH:MM em ini e fim.")
        if self.ini >= self.fim:
            raise ValueError(f"O turno {self.nome} precisa terminar depois de começar.")
        if any(d < 0 or d > 6 for d in self.dias):
            raise ValueError("Dias vão de 0 (domingo) a 6 (sábado).")
        self.dias = sorted(set(self.dias))
        return self


class Agenda(Schema):
    versao: int = 3
    minimo: int = Field(default=1, ge=1)
    horarios: list[Horario] = Field(min_length=1)

    @model_validator(mode="after")
    def sem_sobreposicao(self):
        for i, a in enumerate(self.horarios):
            for b in self.horarios[i + 1 :]:
                if set(a.dias) & set(b.dias) and a.ini < b.fim and b.ini < a.fim:
                    raise ValueError(f"Os turnos {a.nome} e {b.nome} se sobrepõem.")
        return self


# ---------- cadastro ----------
class Despesa(Schema):
    id: TextoOpcional = None
    descricao: str
    valor: float = 0


class Espaco(Schema):
    id: TextoOpcional = None
    nome: str = Field(min_length=1, max_length=80)
    tipo: TipoEspaco = TipoEspaco.CONSULTORIO
    modalidade: Modalidade = Modalidade.TURNO
    capacidade: float = 0
    preco: float = 0
    preco_turno: NumeroOpcional = None
    descricao: str = ""
    obs: str = ""
    despesas: list[Despesa] = []
    # None = usa os turnos da Santé
    agenda: Agenda | None = None


class CustoFixo(Schema):
    id: TextoOpcional = None
    descricao: str
    valor: float = 0


class Custos(Schema):
    fixos: list[CustoFixo] = []
    impostos: float = Field(default=0, ge=0, le=1)
    comissoes: float = Field(default=0, ge=0, le=1)


class Outra(Schema):
    rotulo: str = ""
    url: str


class Profissional(Schema):
    id: TextoOpcional = None
    nome: str = Field(min_length=1, max_length=160)
    profissao: str = ""
    especialidade: str = ""
    registro: str = ""
    ano_formatura: InteiroOpcional = None
    telefone: str = ""
    email: str = ""
    canal: str = ""
    redes: dict[str, str] = {}
    outras: list[Outra] = []
    obs: str = ""


# ---------- operação ----------
class Campanha(Schema):
    id: TextoOpcional = None
    nome: str = Field(min_length=1)
    canal: str = ""
    espacos: list[str] = []
    inicio: DataOpcional = None
    fim: DataOpcional = None
    orcamento: float = 0
    leads: int = 0
    visitas: int = 0
    status: StatusCampanha = StatusCampanha.PLANEJADA
    obs: str = ""


class Contrato(Schema):
    id: TextoOpcional = None
    espaco_id: str
    profissional_id: TextoOpcional = None
    campanha: TextoOpcional = None
    cliente: str = ""
    modalidade: Modalidade
    quantidade: float = 0
    preco: float = 0
    inicio: date
    fim: DataOpcional = None
    status: StatusContrato = StatusContrato.CONFIRMADA
    obs: str = ""


class Agendamento(Schema):
    id: TextoOpcional = None
    espaco_id: str
    data: date
    slots: list[str] = Field(min_length=1)
    tipo: TipoAgendamento = TipoAgendamento.LOCACAO
    profissional_id: TextoOpcional = None
    cliente: str = ""
    valor: float = 0
    status: StatusAgenda = StatusAgenda.CONFIRMADA
    obs: str = ""
    grupo: str = ""

    @field_validator("slots")
    @classmethod
    def formato(cls, v: list[str]) -> list[str]:
        if not all(SLOT.match(s) for s in v):
            raise ValueError('Cada turno deve ter o formato "08:00-12:00".')
        return sorted(set(v))


# ---------- documento inteiro (sante.json) ----------
class Meta(Schema):
    clinica: str = "Santé Consultórios"
    razao_social: str = ""
    endereco: str = ""
    telefone: str = ""
    whatsapp: str = ""
    site: str = ""
    instagram: str = ""
    atualizado_em: DataOpcional = None


class Metas(Schema):
    ocupacao_alvo: float = Field(default=0.6, ge=0, le=1)


class ClinicaDados(Schema):
    """Dados da Santé e meta de ocupação (`meta` e `metas` do sante.json)."""

    meta: Meta = Meta()
    metas: Metas = Metas()


class Documento(Schema):
    meta: Meta = Meta()
    metas: Metas = Metas()
    turnos: Agenda
    espacos: list[Espaco] = []
    custos: Custos = Custos()
    campanhas: list[Campanha] = []
    contratos: list[Contrato] = []
    agendamentos: list[Agendamento] = []
    profissionais: list[Profissional] = []
