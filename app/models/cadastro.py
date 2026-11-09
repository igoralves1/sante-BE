"""Cadastro da casa: clínica, turnos, espaços, despesas, custos fixos e locatários."""

from tortoise import fields
from tortoise.contrib.postgres.fields import ArrayField
from tortoise.models import Model

from app.models.enums import Modalidade, TipoEspaco


class Base(Model):
    criado_em = fields.DatetimeField(auto_now_add=True)
    atualizado_em = fields.DatetimeField(auto_now=True)

    class Meta:
        abstract = True


class Clinica(Base):
    """Dados da Santé e parâmetros gerais (uma linha só). No front: `meta`, `metas` e `custos`."""

    id = fields.IntField(primary_key=True)
    nome = fields.CharField(max_length=120)
    razao_social = fields.CharField(max_length=160, default="")
    endereco = fields.CharField(max_length=200, default="")
    telefone = fields.CharField(max_length=30, default="")
    whatsapp = fields.CharField(max_length=200, default="")
    site = fields.CharField(max_length=200, default="")
    instagram = fields.CharField(max_length=200, default="")
    # meta de ocupação (0 a 1)
    ocupacao_alvo = fields.DecimalField(max_digits=5, decimal_places=4, default=0.6)
    # frações da receita (0 a 1) descontadas antes da margem
    impostos = fields.DecimalField(max_digits=5, decimal_places=4, default=0)
    comissoes = fields.DecimalField(max_digits=5, decimal_places=4, default=0)
    # mínimo de turnos por reserva na agenda da Santé
    turnos_minimo = fields.SmallIntField(default=1)
    dados_atualizados_em = fields.DateField(null=True)

    class Meta:
        table = "clinica"


class Espaco(Base):
    """Sala, piscina ou área administrativa que a Santé aluga (centro de custo)."""

    id = fields.CharField(max_length=40, primary_key=True)
    nome = fields.CharField(max_length=80, unique=True)
    tipo = fields.CharEnumField(TipoEspaco, max_length=30, default=TipoEspaco.CONSULTORIO)
    modalidade = fields.CharEnumField(Modalidade, max_length=10, default=Modalidade.TURNO)
    # unidades vendáveis por mês para quem não usa agenda (Mensal / Administrativo)
    capacidade = fields.DecimalField(max_digits=10, decimal_places=2, default=0)
    preco = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    # valor pedido por turno (receita potencial de cada turno em aberto)
    preco_turno = fields.DecimalField(max_digits=12, decimal_places=2, null=True)
    descricao = fields.TextField(default="")
    obs = fields.TextField(default="")
    # False = usa os turnos da Santé; True = tem turnos próprios na tabela turno
    turnos_proprios = fields.BooleanField(default=False)
    agenda_minimo = fields.SmallIntField(null=True)
    ordem = fields.SmallIntField(default=0)

    turnos: fields.ReverseRelation["Turno"]
    despesas: fields.ReverseRelation["DespesaEspaco"]

    class Meta:
        table = "espaco"
        ordering = ["ordem", "nome"]


class Turno(Model):
    """Horário que pode ser locado. espaco nulo = turno da Santé, vale para todas as salas
    sem turnos próprios. `dias` segue o getDay() do JavaScript: 0 = domingo ... 6 = sábado."""

    id = fields.IntField(primary_key=True)
    espaco = fields.ForeignKeyField(
        "models.Espaco", related_name="turnos", null=True, on_delete=fields.CASCADE
    )
    nome = fields.CharField(max_length=30)
    ini = fields.CharField(max_length=5)  # "08:00"
    fim = fields.CharField(max_length=5)  # "12:00"
    dias = ArrayField("smallint")
    ordem = fields.SmallIntField(default=0)

    class Meta:
        table = "turno"
        ordering = ["ordem", "ini"]

    @property
    def chave(self) -> str:
        return f"{self.ini}-{self.fim}"


class DespesaEspaco(Model):
    """Despesa própria de um espaço (centro de custo)."""

    id = fields.CharField(max_length=40, primary_key=True)
    espaco = fields.ForeignKeyField("models.Espaco", related_name="despesas", on_delete=fields.CASCADE)
    descricao = fields.CharField(max_length=160)
    valor = fields.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        table = "despesa_espaco"


class CustoFixo(Model):
    """Custo fixo mensal da casa (aluguel, energia, recepção...)."""

    id = fields.CharField(max_length=40, primary_key=True)
    descricao = fields.CharField(max_length=160)
    valor = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    ordem = fields.SmallIntField(default=0)

    class Meta:
        table = "custo_fixo"
        ordering = ["ordem"]


class Profissional(Base):
    """Locatário: profissional de saúde que aluga turnos ou salas."""

    id = fields.CharField(max_length=40, primary_key=True)
    nome = fields.CharField(max_length=160, unique=True)
    profissao = fields.CharField(max_length=80, default="")
    especialidade = fields.CharField(max_length=120, default="")
    registro = fields.CharField(max_length=40, default="")  # CRM, CRP, CREFITO...
    ano_formatura = fields.SmallIntField(null=True)
    telefone = fields.CharField(max_length=30, default="")
    email = fields.CharField(max_length=160, default="")
    canal = fields.CharField(max_length=80, default="")  # como conheceu a Santé
    obs = fields.TextField(default="")

    links: fields.ReverseRelation["ProfissionalLink"]

    class Meta:
        table = "profissional"
        ordering = ["nome"]


class ProfissionalLink(Model):
    """Rede social ou site do profissional. rede = instagram, linkedin, ... ou 'outra' (com rótulo)."""

    id = fields.IntField(primary_key=True)
    profissional = fields.ForeignKeyField(
        "models.Profissional", related_name="links", on_delete=fields.CASCADE
    )
    rede = fields.CharField(max_length=20)
    valor = fields.CharField(max_length=300)
    rotulo = fields.CharField(max_length=60, default="")

    class Meta:
        table = "profissional_link"
