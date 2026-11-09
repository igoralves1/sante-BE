"""Schemas da API. Os campos usam camelCase, no mesmo formato do sante.json do front.

Os modelos de entrada validam o que chega. Os de saída (`...Saida`) só documentam o que as rotas
devolvem, para a documentação em /docs; as rotas montam as respostas em app/services/serializar.py.
"""

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

ID = "Identificador. Na criação, pode ficar vazio: a API gera um."
VAZIO = 'Texto vazio ("") quando não há.'


def exemplos(*xs: dict) -> ConfigDict:
    return ConfigDict(json_schema_extra={"examples": list(xs)})


class Schema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


# ---------- erros e respostas simples ----------
class Erro(BaseModel):
    """Erro devolvido pela API. `detail` é uma frase em português, pronta para mostrar na tela."""

    detail: str = Field(description="O que deu errado.", examples=["Espaço e9 não encontrado."])


class ErroValidacao(BaseModel):
    """Dados inválidos. `detail` é uma frase (regra do sistema) ou a lista de campos com erro (validação)."""

    detail: str | list[dict[str, Any]] = Field(
        examples=["Sala 1 não abre 21:00-23:00 em 2026-11-10.", [{"loc": ["body", "nome"], "msg": "Field required", "type": "missing"}]]
    )


class Saude(BaseModel):
    status: str = Field(examples=["ok"])
    banco: str = Field(examples=["ok"])


class Excluidos(BaseModel):
    excluidos: int = Field(description="Quantos registros foram excluídos.", examples=[12])


class Importado(BaseModel):
    importado: dict[str, int] = Field(
        description="Quantos registros ficaram em cada tabela depois da importação.",
        examples=[{"espaco": 8, "turno": 3, "contrato": 12, "agendamento": 40, "profissional": 9}],
    )


# ---------- turnos ----------
class Horario(Schema):
    """Turno que pode ser locado (ex.: Manhã, 08:00 a 12:00, de segunda a sábado)."""

    model_config = exemplos({"nome": "Manhã", "ini": "08:00", "fim": "12:00", "dias": [1, 2, 3, 4, 5, 6]})

    nome: str = Field(min_length=1, max_length=30, description="Nome do turno.")
    ini: str = Field(description="Início, HH:MM.", examples=["08:00"])
    fim: str = Field(description="Fim, HH:MM. Precisa ser depois do início.", examples=["12:00"])
    dias: list[int] = Field(min_length=1, description="Dias em que o turno abre: 0 = domingo ... 6 = sábado.")

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
    """Conjunto de turnos. Turnos que abrem no mesmo dia não podem se sobrepor."""

    model_config = exemplos({
        "versao": 3,
        "minimo": 1,
        "horarios": [
            {"nome": "Manhã", "ini": "08:00", "fim": "12:00", "dias": [1, 2, 3, 4, 5, 6]},
            {"nome": "Tarde", "ini": "13:00", "fim": "17:00", "dias": [1, 2, 3, 4, 5]},
            {"nome": "Noite", "ini": "17:00", "fim": "21:00", "dias": [1, 2, 3, 4, 5]},
        ],
    })

    versao: int = Field(default=3, description="Versão do formato da agenda.")
    minimo: int = Field(default=1, ge=1, description="Mínimo de turnos por locação.")
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
    """Despesa própria de um espaço (centro de custo), por mês."""

    id: TextoOpcional = Field(None, description=ID)
    descricao: str = Field(examples=["Manutenção da piscina"])
    valor: float = Field(0, description="R$ por mês.", examples=[350])


class Espaco(Schema):
    """Sala, piscina ou área que a Santé aluga (centro de custo)."""

    model_config = exemplos({
        "id": "e1",
        "nome": "Sala 1",
        "tipo": "Consultório",
        "modalidade": "Turno",
        "capacidade": 1,
        "preco": 120,
        "precoTurno": None,
        "descricao": "Consultório com maca e pia.",
        "obs": "",
        "despesas": [],
        "agenda": None,
    })

    id: TextoOpcional = Field(None, description=ID)
    nome: str = Field(min_length=1, max_length=80, description="Nome único do espaço.")
    tipo: TipoEspaco = Field(TipoEspaco.CONSULTORIO, description="Tipo do espaço.")
    modalidade: Modalidade = Field(
        Modalidade.TURNO,
        description="Como é cobrado: por hora, por turno ou por mês. Espaços `Mensal` e `Administrativo` não usam agenda.",
    )
    capacidade: float = Field(0, description="Pessoas atendidas ao mesmo tempo.")
    preco: float = Field(0, description="Preço da unidade (hora, turno ou mês), em R$.")
    preco_turno: NumeroOpcional = Field(None, description="Preço de um turno, quando diferente de `preco`. Usado na receita não realizada.")
    descricao: str = ""
    obs: str = ""
    despesas: list[Despesa] = []
    agenda: Agenda | None = Field(None, description="Turnos próprios do espaço. `null` = usa os turnos da Santé (`/api/turnos`).")


class CustoFixo(Schema):
    """Custo fixo mensal da casa (aluguel, energia, recepção...)."""

    id: TextoOpcional = Field(None, description=ID)
    descricao: str = Field(examples=["Aluguel"])
    valor: float = Field(0, description="R$ por mês.", examples=[6500])


class Custos(Schema):
    """Custos fixos da casa e percentuais sobre a receita."""

    model_config = exemplos({
        "fixos": [{"id": "cf1", "descricao": "Aluguel", "valor": 6500}],
        "impostos": 0.06,
        "comissoes": 0.05,
    })

    fixos: list[CustoFixo] = []
    impostos: float = Field(default=0, ge=0, le=1, description="Fração da receita (0,06 = 6%).")
    comissoes: float = Field(default=0, ge=0, le=1, description="Fração da receita (0,05 = 5%).")


class Outra(Schema):
    rotulo: str = Field("", description="Nome do link (ex.: Doctoralia).")
    url: str


class Profissional(Schema):
    """Locatário: profissional de saúde que aluga turnos ou salas. Contém dados pessoais (LGPD)."""

    model_config = exemplos({
        "nome": "Dra. Ana Exemplo",
        "profissao": "Psicóloga",
        "especialidade": "TCC",
        "registro": "CRP 15/0000",
        "anoFormatura": 2024,
        "telefone": "(82) 90000-0000",
        "email": "ana@exemplo.com",
        "canal": "Instagram",
        "redes": {"instagram": "https://instagram.com/exemplo"},
        "outras": [],
        "obs": "",
    })

    id: TextoOpcional = Field(None, description=ID)
    nome: str = Field(min_length=1, max_length=160, description="Nome único (sem diferenciar maiúsculas).")
    profissao: str = ""
    especialidade: str = ""
    registro: str = Field("", description="Registro no conselho (CRM, CRP, CREFITO...).")
    ano_formatura: InteiroOpcional = None
    telefone: str = ""
    email: str = ""
    canal: str = Field("", description="Como chegou até a Santé.")
    redes: dict[str, str] = Field({}, description="Rede → link (instagram, linkedin, facebook, site...).")
    outras: list[Outra] = Field([], description="Outros links, com rótulo.")
    obs: str = ""


# ---------- operação ----------
class Campanha(Schema):
    """Ação comercial (anúncio, parceria, evento) e seus resultados."""

    model_config = exemplos({
        "nome": "Anúncio Instagram novembro",
        "canal": "Instagram",
        "espacos": ["e1", "e2"],
        "inicio": "2026-11-01",
        "fim": "2026-11-30",
        "orcamento": 600,
        "leads": 0,
        "visitas": 0,
        "status": "Planejada",
        "obs": "",
    })

    id: TextoOpcional = Field(None, description=ID)
    nome: str = Field(min_length=1)
    canal: str = ""
    espacos: list[str] = Field([], description="IDs dos espaços divulgados.")
    inicio: DataOpcional = None
    fim: DataOpcional = None
    orcamento: float = Field(0, description="R$.")
    leads: int = 0
    visitas: int = 0
    status: StatusCampanha = StatusCampanha.PLANEJADA
    obs: str = ""


class Contrato(Schema):
    """Locação recorrente: quantidade de unidades (horas, turnos ou meses) por mês."""

    model_config = exemplos({
        "espacoId": "e1",
        "profissionalId": "p1",
        "cliente": "Dra. Ana Exemplo",
        "modalidade": "Turno",
        "quantidade": 8,
        "preco": 120,
        "inicio": "2026-11-01",
        "fim": "",
        "status": "Confirmada",
        "campanha": "",
        "obs": "",
    })

    id: TextoOpcional = Field(None, description=ID)
    espaco_id: str = Field(description="ID do espaço.")
    profissional_id: TextoOpcional = Field(None, description="ID do locatário.")
    campanha: TextoOpcional = Field(None, description="ID da campanha que trouxe o contrato.")
    cliente: str = Field("", description="Nome de quem loca (usado quando não há locatário cadastrado).")
    modalidade: Modalidade
    quantidade: float = Field(0, description="Unidades por mês.")
    preco: float = Field(0, description="Preço da unidade, em R$.")
    inicio: date
    fim: DataOpcional = Field(None, description="Vazio = sem data para terminar.")
    status: StatusContrato = StatusContrato.CONFIRMADA
    obs: str = ""


class Agendamento(Schema):
    """Turnos de um dia na agenda de um espaço: locação a um profissional, ou bloqueio ("Não disponível")."""

    model_config = exemplos(
        {
            "espacoId": "e1",
            "data": "2026-11-10",
            "slots": ["08:00-12:00"],
            "tipo": "locacao",
            "profissionalId": "p1",
            "valor": 120,
            "status": "Confirmada",
            "obs": "",
            "grupo": "",
        },
        {"espacoId": "e6", "data": "2026-11-11", "slots": ["17:00-21:00"], "tipo": "bloqueio", "obs": "Manutenção"},
    )

    id: TextoOpcional = Field(None, description=ID)
    espaco_id: str = Field(description="ID do espaço. Precisa ser um espaço que usa agenda.")
    data: date
    slots: list[str] = Field(min_length=1, description='Turnos do dia, no formato "HH:MM-HH:MM". Precisam abrir nesse dia da semana.')
    tipo: TipoAgendamento = Field(
        TipoAgendamento.LOCACAO,
        description="`locacao` = turno locado; `bloqueio` = turno não disponível (sai da capacidade do mês).",
    )
    profissional_id: TextoOpcional = Field(None, description="ID do locatário. Obrigatório numa locação sem `cliente`.")
    cliente: str = Field("", description="Nome de quem loca. Preenchido com o nome do locatário quando vazio.")
    valor: float = Field(0, description="R$ cobrados por este dia. Zero num bloqueio.")
    status: StatusAgenda = StatusAgenda.CONFIRMADA
    obs: str = ""
    grupo: str = Field("", description="Mesmo valor nos dias criados juntos numa repetição (para excluir todos de uma vez).")

    @field_validator("slots")
    @classmethod
    def formato(cls, v: list[str]) -> list[str]:
        if not all(SLOT.match(s) for s in v):
            raise ValueError('Cada turno deve ter o formato "08:00-12:00".')
        return sorted(set(v))


# ---------- documento inteiro (sante.json) ----------
class Meta(Schema):
    """Dados da Santé (bloco `meta` do sante.json)."""

    clinica: str = "Santé Consultórios"
    razao_social: str = ""
    endereco: str = ""
    telefone: str = ""
    whatsapp: str = ""
    site: str = ""
    instagram: str = ""
    atualizado_em: DataOpcional = Field(None, description="Data da última revisão dos dados.")


class Metas(Schema):
    ocupacao_alvo: float = Field(default=0.6, ge=0, le=1, description="Ocupação desejada (0,6 = 60%).")


class ClinicaDados(Schema):
    """Dados da Santé e meta de ocupação (`meta` e `metas` do sante.json)."""

    meta: Meta = Meta()
    metas: Metas = Metas()


class Documento(Schema):
    """O sistema inteiro, no formato do arquivo `public/data/sante.json` do front."""

    meta: Meta = Meta()
    metas: Metas = Metas()
    turnos: Agenda = Field(description="Turnos da Santé.")
    espacos: list[Espaco] = []
    custos: Custos = Custos()
    campanhas: list[Campanha] = []
    contratos: list[Contrato] = []
    agendamentos: list[Agendamento] = []
    profissionais: list[Profissional] = []


# ---------- respostas (só para a documentação) ----------
class DespesaSaida(Despesa):
    id: str


class EspacoSaida(Espaco):
    id: str
    despesas: list[DespesaSaida] = []


class CustoFixoSaida(CustoFixo):
    id: str


class CustosSaida(Custos):
    fixos: list[CustoFixoSaida] = []


class ProfissionalSaida(Profissional):
    id: str
    ano_formatura: int | str = Field("", description=f"Ano em que se formou. {VAZIO}")
    criado_em: str = Field("", description="Data do cadastro (AAAA-MM-DD).")


class CampanhaSaida(Campanha):
    id: str
    inicio: str = Field("", description=f"AAAA-MM-DD. {VAZIO}")
    fim: str = Field("", description=f"AAAA-MM-DD. {VAZIO}")


class ContratoSaida(Contrato):
    id: str
    profissional_id: str = Field("", description=f"ID do locatário. {VAZIO}")
    campanha: str = Field("", description=f"ID da campanha. {VAZIO}")
    inicio: str = Field(description="AAAA-MM-DD.")
    fim: str = Field("", description=f"AAAA-MM-DD. {VAZIO}")


class AgendamentoSaida(Agendamento):
    id: str
    data: str = Field(description="AAAA-MM-DD.")
    profissional_id: str = Field("", description=f"ID do locatário. {VAZIO}")


class Capacidade(Schema):
    """Turnos (ou horas) de um espaço num mês, contando os dias reais do calendário."""

    model_config = exemplos({
        "espacoId": "e1",
        "mes": "2026-11",
        "usaAgenda": True,
        "unidade": "turnos",
        "noCalendario": 71,
        "naoDisponiveis": 4,
        "emAberto": 67,
        "ocupados": 2,
        "livres": 65,
        "ocupacao": 0.0299,
        "profissionais": 1,
        "receitaLocada": 240,
        "receitaBloqueada": 480,
    })

    espaco_id: str
    mes: str = Field(description="AAAA-MM.")
    usa_agenda: bool = Field(description="Falso para espaços `Mensal` e `Administrativo`; os demais campos vêm zerados.")
    unidade: str = Field(description="`turnos` ou `horas` (espaços cobrados por hora).")
    no_calendario: float = Field(description="Turnos que abrem nos dias do mês.")
    nao_disponiveis: float = Field(description="Turnos bloqueados (\"Não disponível\").")
    em_aberto: float = Field(description="No calendário − não disponíveis. É a capacidade real do mês.")
    ocupados: float = Field(description="Turnos locados.")
    livres: float = Field(description="Em aberto − ocupados.")
    ocupacao: float = Field(description="Ocupados ÷ em aberto (0 a 1).")
    profissionais: int = Field(description="Locatários diferentes no mês.")
    receita_locada: float = Field(description="Soma dos valores das locações, em R$.")
    receita_bloqueada: float = Field(description="Receita não realizada: não disponíveis × preço do turno.")


class DocumentoSaida(Documento):
    espacos: list[EspacoSaida] = []
    custos: CustosSaida = CustosSaida()
    campanhas: list[CampanhaSaida] = []
    contratos: list[ContratoSaida] = []
    agendamentos: list[AgendamentoSaida] = []
    profissionais: list[ProfissionalSaida] = []


# ---------- base de dados ----------
class Consulta(Schema):
    """Uma consulta SQL só de leitura."""

    model_config = exemplos({"sql": "SELECT nome, tipo, modalidade, preco FROM espaco ORDER BY ordem", "limite": 500})

    sql: str = Field(min_length=1, max_length=20000, description="Um comando: SELECT, WITH, EXPLAIN, SHOW ou VALUES.")
    limite: int = Field(500, ge=1, le=5000, description="Máximo de linhas na resposta.")


class Coluna(Schema):
    nome: str
    tipo: str = Field(description="Tipo no PostgreSQL.", examples=["varchar", "numeric", "_int2"])


class Resultado(Schema):
    """Resultado de uma consulta: colunas e linhas (cada linha é uma lista, na ordem das colunas)."""

    model_config = exemplos({
        "colunas": [{"nome": "nome", "tipo": "varchar"}, {"nome": "preco", "tipo": "numeric"}],
        "linhas": [["Sala 1", 120], ["Piscina", 90]],
        "quantidade": 2,
        "total": None,
        "truncado": False,
        "tempoMs": 3.2,
        "comando": "SELECT",
    })

    colunas: list[Coluna]
    linhas: list[list[Any]]
    quantidade: int = Field(description="Linhas nesta resposta.")
    total: int | None = Field(None, description="Linhas na tabela (com a busca aplicada). Só na navegação por tabela.")
    truncado: bool = Field(description="Há mais linhas além das que vieram.")
    tempo_ms: float = Field(description="Tempo da consulta, em milissegundos.")
    comando: str = Field(description="Primeira palavra do comando (SELECT, WITH...).")


class ColunaEsquema(Schema):
    nome: str
    tipo: str = Field(examples=["character varying(40)", "numeric(10,2)", "smallint[]"])
    nulo: bool = Field(description="Aceita NULL.")
    padrao: str | None = Field(None, description="Valor padrão no banco.")
    pk: bool = Field(description="Faz parte da chave primária.")
    fk: dict[str, str] | None = Field(None, description="Chave estrangeira: `{tabela, coluna}` referenciada.")


class Indice(Schema):
    nome: str
    definicao: str


class TabelaEsquema(Schema):
    nome: str
    grupo: str = Field(description="cadastro, operacao, mercado ou sistema.")
    descricao: str
    linhas: int = Field(description="Número de linhas agora.")
    colunas: list[ColunaEsquema]
    chave_primaria: list[str]
    unicas: list[list[str]] = Field(description="Restrições UNIQUE (cada uma, uma lista de colunas).")
    indices: list[Indice]


class Relacao(Schema):
    nome: str = Field(description="Nome da chave estrangeira no banco.")
    de: str = Field(description="Tabela que referencia.")
    colunas: list[str]
    para: str = Field(description="Tabela referenciada.")
    ref_colunas: list[str]
    ao_excluir: str = Field(description="O que acontece ao excluir a linha referenciada (CASCADE, RESTRICT, SET NULL...).")


class Esquema(Schema):
    banco: str = Field(examples=["PostgreSQL 18.1"])
    gerado_em: str
    grupos: dict[str, str] = Field(description="Código do grupo → nome para mostrar.")
    tabelas: list[TabelaEsquema]
    relacoes: list[Relacao]
