"""Dados do próprio sistema (não do negócio)."""

from tortoise import fields
from tortoise.models import Model


class DiagramaPosicao(Model):
    """Posição de cada tabela no diagrama do banco, arrumada à mão na página Diagrama do banco."""

    tabela = fields.CharField(max_length=63, primary_key=True)
    x = fields.FloatField()
    y = fields.FloatField()
    atualizado_em = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "diagrama_posicao"
