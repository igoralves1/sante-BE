"""Análise de mercado: concorrentes e monitor social (coletas manuais de páginas públicas)."""

from tortoise import fields
from tortoise.contrib.postgres.fields import ArrayField
from tortoise.models import Model


class Coleta(Model):
    """Data e nota de cada coleta manual (fonte = 'concorrentes' ou 'social')."""

    id = fields.IntField(primary_key=True)
    fonte = fields.CharField(max_length=30, unique=True)
    coletado_em = fields.DateField()
    nota = fields.TextField(default="")

    class Meta:
        table = "coleta"


class Concorrente(Model):
    """Player do mercado de Maceió. proprio = True para a própria Santé."""

    id = fields.CharField(max_length=40, primary_key=True)
    nome = fields.CharField(max_length=160)
    proprio = fields.BooleanField(default=False)
    tipo = fields.CharField(max_length=30, default="")  # direto, indireto...
    local = fields.CharField(max_length=200, default="")
    regiao = fields.CharField(max_length=80, default="")
    modalidades = fields.CharField(max_length=200, default="")
    preco = fields.CharField(max_length=300, default="")
    horario = fields.CharField(max_length=200, default="")
    diferenciais = fields.TextField(default="")
    reserva = fields.CharField(max_length=120, default="")
    ameaca = fields.CharField(max_length=20, null=True)
    site = fields.CharField(max_length=300, default="")
    instagram = fields.CharField(max_length=120, default="")
    ig = fields.JSONField(null=True)  # {seguidores, seguindo, posts}
    google = fields.JSONField(null=True)  # {nota, avaliacoes, categoria}
    anuncios_meta = fields.BooleanField(default=False)
    modalidades_n = fields.SmallIntField(null=True)
    preco_hora_min = fields.IntField(null=True)
    horas_semana = fields.IntField(null=True)
    ordem = fields.SmallIntField(default=0)

    class Meta:
        table = "concorrente"
        ordering = ["ordem"]


class PrecoHora(Model):
    """Preço por hora anunciado por um concorrente (cada faixa ou serviço numa linha)."""

    id = fields.IntField(primary_key=True)
    concorrente = fields.ForeignKeyField("models.Concorrente", related_name="precos_hora", on_delete=fields.CASCADE)
    label = fields.CharField(max_length=120)
    valor = fields.DecimalField(max_digits=10, decimal_places=2)
    sub = fields.CharField(max_length=160, default="")
    ordem = fields.SmallIntField(default=0)

    class Meta:
        table = "preco_hora"
        ordering = ["ordem"]


class BuscaMapa(Model):
    """Resultado de uma busca no Google Maps: posição da Santé e quem aparece no topo."""

    id = fields.IntField(primary_key=True)
    busca = fields.CharField(max_length=200)
    posicao_sante = fields.SmallIntField(null=True)
    topo = ArrayField("text")
    ordem = fields.SmallIntField(default=0)

    class Meta:
        table = "busca_mapa"
        ordering = ["ordem"]


class AvaliacaoSite(Model):
    """Notas do PageSpeed (Lighthouse) do site de um concorrente."""

    id = fields.IntField(primary_key=True)
    concorrente = fields.ForeignKeyField("models.Concorrente", related_name="avaliacoes_site", on_delete=fields.CASCADE)
    site = fields.CharField(max_length=200)
    desempenho = fields.SmallIntField(null=True)
    acessibilidade = fields.SmallIntField(null=True)
    boas_praticas = fields.SmallIntField(null=True)
    seo = fields.SmallIntField(null=True)
    lcp = fields.DecimalField(max_digits=6, decimal_places=2, null=True)
    paginas = fields.IntField(null=True)
    dominio = fields.CharField(max_length=20, default="")  # data de registro do domínio
    obs = fields.TextField(default="")
    ordem = fields.SmallIntField(default=0)

    class Meta:
        table = "avaliacao_site"
        ordering = ["ordem"]


class TrafegoSite(Model):
    """Consulta de tráfego no Similarweb."""

    id = fields.IntField(primary_key=True)
    site = fields.CharField(max_length=200)
    resultado = fields.TextField(default="")
    ordem = fields.SmallIntField(default=0)

    class Meta:
        table = "trafego_site"
        ordering = ["ordem"]


class RedeSocial(Model):
    """Rede social acompanhada no monitor (Instagram, Facebook, YouTube...) e por que ela importa."""

    id = fields.CharField(max_length=20, primary_key=True)  # instagram, facebook, youtube
    nome = fields.CharField(max_length=40)
    contas_br = fields.CharField(max_length=40, default="")
    fonte = fields.CharField(max_length=200, default="")
    porque = fields.TextField(default="")
    ordem = fields.SmallIntField(default=0)

    class Meta:
        table = "rede_social"
        ordering = ["ordem"]


class PerfilSocial(Model):
    """Perfil de uma empresa numa rede. status: ativo, parado, nao-encontrado, perfil-pessoal."""

    id = fields.CharField(max_length=60, primary_key=True)
    concorrente = fields.ForeignKeyField("models.Concorrente", related_name="perfis", on_delete=fields.CASCADE)
    rede = fields.ForeignKeyField("models.RedeSocial", related_name="perfis", on_delete=fields.RESTRICT)
    handle = fields.CharField(max_length=120, default="")
    nome = fields.CharField(max_length=160, default="")
    seguidores = fields.IntField(null=True)
    seguindo = fields.IntField(null=True)
    publicacoes = fields.IntField(null=True)
    checkins = fields.IntField(null=True)
    falando_sobre = fields.IntField(null=True)
    url = fields.CharField(max_length=300, default="")
    status = fields.CharField(max_length=20, default="ativo")
    obs = fields.TextField(default="")
    ordem = fields.SmallIntField(default=0)

    class Meta:
        table = "perfil_social"
        ordering = ["ordem"]


class PostSocial(Model):
    """Publicação recente de um perfil: data, tipo, curtidas e legenda."""

    id = fields.CharField(max_length=60, primary_key=True)
    perfil = fields.ForeignKeyField("models.PerfilSocial", related_name="posts", on_delete=fields.CASCADE)
    data = fields.DateField()
    tipo = fields.CharField(max_length=10)  # reel, foto
    curtidas = fields.IntField(null=True)  # nulo = curtidas ocultas
    legenda = fields.TextField(default="")
    url = fields.CharField(max_length=300, default="")
    ordem = fields.IntField(default=0)

    class Meta:
        table = "post_social"
        ordering = ["ordem", "-data"]


class BuscaYoutube(Model):
    """Busca no YouTube por um termo do setor e os vídeos em destaque."""

    id = fields.IntField(primary_key=True)
    termo = fields.CharField(max_length=200)
    analisados = fields.IntField(default=0)
    do_setor = fields.IntField(default=0)
    resumo = fields.TextField(default="")
    destaques = fields.JSONField(default=list)  # [{titulo, canal, views}]
    ordem = fields.SmallIntField(default=0)

    class Meta:
        table = "busca_youtube"
        ordering = ["ordem"]
