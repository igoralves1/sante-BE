"""Operação: contratos (carteira), agenda de turnos e campanhas."""

from tortoise import fields
from tortoise.contrib.postgres.fields import ArrayField
from tortoise.models import Model

from app.models.cadastro import Base
from app.models.enums import (
    Modalidade,
    StatusAgenda,
    StatusCampanha,
    StatusContrato,
    TipoAgendamento,
)


class Campanha(Base):
    id = fields.CharField(max_length=40, primary_key=True)
    nome = fields.CharField(max_length=200)
    canal = fields.CharField(max_length=120, default="")
    inicio = fields.DateField(null=True)
    fim = fields.DateField(null=True)
    orcamento = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    leads = fields.IntField(default=0)
    visitas = fields.IntField(default=0)
    status = fields.CharEnumField(StatusCampanha, max_length=20, default=StatusCampanha.PLANEJADA)
    obs = fields.TextField(default="")
    espacos = fields.ManyToManyField(
        "models.Espaco", related_name="campanhas", through="campanha_espaco"
    )

    class Meta:
        table = "campanha"


class Contrato(Base):
    """Locação recorrente: quantidade de unidades (horas, turnos ou meses) por mês."""

    id = fields.CharField(max_length=40, primary_key=True)
    espaco = fields.ForeignKeyField("models.Espaco", related_name="contratos", on_delete=fields.RESTRICT)
    profissional = fields.ForeignKeyField(
        "models.Profissional", related_name="contratos", null=True, on_delete=fields.SET_NULL
    )
    campanha = fields.ForeignKeyField(
        "models.Campanha", related_name="contratos", null=True, on_delete=fields.SET_NULL
    )
    cliente = fields.CharField(max_length=160, default="")
    modalidade = fields.CharEnumField(Modalidade, max_length=10)
    quantidade = fields.DecimalField(max_digits=10, decimal_places=2, default=0)
    preco = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    inicio = fields.DateField()
    fim = fields.DateField(null=True)  # nulo = sem término
    status = fields.CharEnumField(StatusContrato, max_length=20, default=StatusContrato.CONFIRMADA)
    obs = fields.TextField(default="")

    class Meta:
        table = "contrato"
        indexes = (("espaco_id", "inicio"),)


class Agendamento(Base):
    """Turnos de um dia na agenda de um espaço: locação a um profissional ou "Não disponível"."""

    id = fields.CharField(max_length=40, primary_key=True)
    espaco = fields.ForeignKeyField("models.Espaco", related_name="agendamentos", on_delete=fields.CASCADE)
    data = fields.DateField()
    slots = ArrayField("text")  # ["08:00-12:00", "14:00-18:00"]
    tipo = fields.CharEnumField(TipoAgendamento, max_length=10, default=TipoAgendamento.LOCACAO)
    profissional = fields.ForeignKeyField(
        "models.Profissional", related_name="agendamentos", null=True, on_delete=fields.SET_NULL
    )
    cliente = fields.CharField(max_length=160, default="")
    valor = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = fields.CharEnumField(StatusAgenda, max_length=20, default=StatusAgenda.CONFIRMADA)
    obs = fields.TextField(default="")
    # agendamentos criados juntos ("repetir no mês/ano") têm o mesmo grupo
    grupo = fields.CharField(max_length=40, default="", db_index=True)

    class Meta:
        table = "agendamento"
        indexes = (("espaco_id", "data"),)
