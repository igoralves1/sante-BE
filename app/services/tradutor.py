"""Traduz perguntas em português para SQL do PostgreSQL, com o Claude (API da Anthropic).

Só a estrutura do banco (tabelas, colunas, tipos, relações e valores possíveis) e a pergunta vão
para a Anthropic. Nenhuma linha de dado sai do servidor: a consulta gerada roda aqui, no papel só
de leitura.
"""

import json
import logging
import os

import anthropic
import asyncpg
from fastapi import HTTPException
from tortoise.models import Model

from app import models as m
from app.config import get_settings

log = logging.getLogger(__name__)

MODELO = "claude-opus-5-5"
TENTATIVAS = 3

FORMATO = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "pode_responder": {"type": "boolean"},
            "sql": {"type": "string"},
            "explicacao": {"type": "string"},
        },
        "required": ["pode_responder", "sql", "explicacao"],
        "additionalProperties": False,
    },
}

INSTRUCOES = """\
Você traduz perguntas em português sobre o sistema de gestão da Santé Consultórios (Maceió) em \
uma consulta SQL para PostgreSQL 18. Quem pergunta é a equipe da clínica, sem conhecimento de SQL. \
A consulta roda numa conexão só de leitura e o resultado aparece numa tabela na tela.

Como escrever a consulta:
- Um único comando, só de leitura: SELECT, ou WITH ... SELECT. A conexão recusa qualquer escrita.
- Use só as tabelas e colunas do esquema abaixo. Se a pergunta não puder ser respondida com elas, \
devolva pode_responder = false, sql vazio, e diga na explicação o que falta.
- Mostre nomes, não IDs: junte com espaco, profissional, campanha etc. para exibir o nome.
- Dê às colunas do resultado nomes curtos em português, em snake_case (AS receita_mensal).
- Ordene o resultado de um jeito útil. Numa lista sem limite pedido, use LIMIT 200.
- Datas relativas ("este mês", "hoje", "ano passado") a partir de current_date (fuso America/Maceio).
- Arredonde valores em reais com round(x, 2) e percentuais com round(100 * x, 1).
- Compare textos com ILIKE, para não depender de maiúsculas.
- Em locatários (profissional) há dados pessoais: selecione só as colunas que a pergunta pede.
- Se a pergunta for ambígua, escolha a leitura mais provável e diga a premissa na explicação.

Como o negócio funciona:
- espaco: sala, piscina ou área que a Santé aluga (centro de custo). modalidade diz como é cobrado \
(Hora, Turno ou Mensal). Espaços Mensal e do tipo Administrativo não usam agenda.
- turno: horários que podem ser locados. espaco_id NULL = turnos da Santé, usados por todos os \
espaços com turnos_proprios = false; os outros espaços usam os próprios turnos. dias é smallint[] \
com 0 = domingo ... 6 = sábado, a mesma convenção de extract(dow from data).
- agendamento: um dia na agenda de um espaço. slots é text[] com turnos "HH:MM-HH:MM". \
tipo = 'locacao' é turno locado a um profissional (valor = R$ do dia); tipo = 'bloqueio' é turno \
"não disponível" (sai da capacidade do mês). status = 'Cancelada' não conta. cardinality(slots) \
dá o número de turnos do dia. grupo liga os dias criados numa mesma repetição.
- Capacidade do mês de um espaço: turnos no calendário (turnos que abrem em cada dia do mês) \
menos os não disponíveis = em aberto; ocupados = turnos locados; ocupação = ocupados ÷ em aberto. \
Para contar turnos no calendário, gere os dias com generate_series e cruze com turno.dias.
- contrato: locação recorrente. Valor mensal = quantidade * preco. Em vigor num mês se \
inicio <= último dia do mês, (fim IS NULL OR fim >= primeiro dia do mês) e status <> 'Cancelada'.
- clinica: uma linha só, com ocupacao_alvo, impostos e comissoes como frações (0,06 = 6%).
- custo_fixo e despesa_espaco: custos mensais (da casa e de cada espaço).
- campanha: ações comerciais; campanha_espaco liga campanhas a espaços.
- concorrente, preco_hora, perfil_social, post_social, rede_social, busca_mapa, avaliacao_site, \
trafego_site, busca_youtube, coleta: análise de mercado (coletas manuais de páginas públicas).
- aerich e diagrama_posicao são internos do sistema.

Na explicação, uma ou duas frases em português simples: o que a consulta mostra e as premissas \
que você assumiu. Sem jargão de SQL.
"""


def disponivel() -> bool:
    return bool(get_settings().anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


_cliente: anthropic.AsyncAnthropic | None = None


def cliente() -> anthropic.AsyncAnthropic:
    global _cliente
    if _cliente is None:
        _cliente = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key or None, timeout=90.0)
    return _cliente


def _valores_enum() -> dict[tuple[str, str], list[str]]:
    """(tabela, coluna) -> valores aceitos, lidos dos campos de enum dos modelos."""
    out = {}
    for nome in dir(m):
        modelo = getattr(m, nome)
        if not (isinstance(modelo, type) and issubclass(modelo, Model)) or modelo._meta.abstract:
            continue
        for campo, f in modelo._meta.fields_map.items():
            tipo = getattr(f, "enum_type", None)
            if tipo is not None:
                out[(modelo._meta.db_table, getattr(f, "source_field", None) or campo)] = [v.value for v in tipo]
    return out


def descrever_esquema(esquema: dict) -> str:
    """Texto estável (mesma entrada, mesmo texto) para o prompt ficar em cache."""
    enums = _valores_enum()
    linhas = []
    for t in sorted(esquema["tabelas"], key=lambda t: (t["grupo"], t["nome"])):
        linhas.append(f"\nTABELA {t['nome']} ({t['grupo']}) - {t['descricao']}")
        for c in t["colunas"]:
            extra = []
            if c["pk"]:
                extra.append("PK")
            if c["fk"]:
                extra.append(f"FK -> {c['fk']['tabela']}.{c['fk']['coluna']}")
            if not c["nulo"]:
                extra.append("NOT NULL")
            valores = enums.get((t["nome"], c["nome"]))
            if valores:
                extra.append("valores: " + ", ".join(f"'{v}'" for v in valores))
            linhas.append(f"  {c['nome']} {c['tipo']}" + (f"  [{'; '.join(extra)}]" if extra else ""))
    return "ESQUEMA DO BANCO (schema public):" + "\n".join(linhas)


def _pedido(pergunta: str, historico: list[dict], sql_atual: str) -> str:
    partes = []
    if historico:
        partes.append("Perguntas anteriores nesta conversa (use como contexto para a nova pergunta):")
        for h in historico[-6:]:
            partes.append(f"- Pergunta: {h['pergunta']}\n  SQL: {h['sql']}")
    if sql_atual.strip():
        partes.append(f"SQL que está no editor agora (a pergunta pode pedir para ajustá-lo):\n{sql_atual.strip()}")
    partes.append(f"Nova pergunta: {pergunta.strip()}")
    return "\n\n".join(partes)


async def _validar(sql: str) -> str | None:
    """Prepara a consulta no papel só de leitura, sem executar. Devolve o erro do PostgreSQL, se houver."""
    from app.routers.banco import somente_leitura

    try:
        async with somente_leitura() as con:
            await con.prepare(sql)
    except asyncpg.PostgresError as e:
        return str(e)
    return None


async def traduzir(pergunta: str, historico: list[dict], sql_atual: str, esquema: dict) -> dict:
    if not disponivel():
        raise HTTPException(
            503,
            "A tradução para SQL precisa de uma chave da API da Anthropic. "
            "Coloque ANTHROPIC_API_KEY no arquivo .env do sante-BE e reinicie a API.",
        )
    system = [
        {"type": "text", "text": INSTRUCOES},
        # o esquema muda raramente: fica no cache e as próximas perguntas saem mais baratas
        {"type": "text", "text": descrever_esquema(esquema), "cache_control": {"type": "ephemeral"}},
    ]
    mensagens: list[dict] = [{"role": "user", "content": _pedido(pergunta, historico, sql_atual)}]

    for tentativa in range(1, TENTATIVAS + 1):
        try:
            r = await cliente().beta.messages.create(
                model=MODELO,
                max_tokens=16000,
                system=system,
                messages=mensagens,
                output_config={"effort": "medium", "format": FORMATO},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError:
            raise HTTPException(503, "A chave da API da Anthropic (ANTHROPIC_API_KEY) foi recusada.") from None
        except anthropic.PermissionDeniedError:
            raise HTTPException(503, "A chave da API da Anthropic não tem permissão para este modelo.") from None
        except anthropic.RateLimitError:
            raise HTTPException(429, "Muitas perguntas seguidas. Espere alguns segundos e tente de novo.") from None
        except anthropic.APIConnectionError:
            raise HTTPException(503, "Não foi possível falar com a API da Anthropic. Confira a internet do servidor.") from None
        except anthropic.APIStatusError as e:
            log.warning("Erro da API da Anthropic (%s): %s", e.status_code, e.message)
            raise HTTPException(502, f"A API da Anthropic respondeu com erro ({e.status_code}). Tente de novo.") from None

        u = r.usage
        log.info(
            "traduzir: tentativa %s, modelo %s, entrada %s (cache lido %s, criado %s), saída %s",
            tentativa, r.model, u.input_tokens, u.cache_read_input_tokens, u.cache_creation_input_tokens, u.output_tokens,
        )
        if r.stop_reason == "refusal":
            raise HTTPException(422, "O assistente não quis responder esta pergunta. Tente escrever de outro jeito.")
        if r.stop_reason == "max_tokens":
            raise HTTPException(502, "A resposta do assistente ficou longa demais. Tente uma pergunta mais simples.")
        texto = next((b.text for b in r.content if b.type == "text"), "")
        try:
            dados = json.loads(texto)
        except json.JSONDecodeError:
            raise HTTPException(502, "O assistente devolveu uma resposta inválida. Tente de novo.") from None

        sql = dados["sql"].strip().rstrip(";").strip()
        if not dados["pode_responder"] or not sql:
            return {"pode_responder": False, "sql": "", "explicacao": dados["explicacao"], "tentativas": tentativa, "modelo": r.model}

        erro = await _validar(sql)
        if erro is None:
            return {"pode_responder": True, "sql": sql + ";", "explicacao": dados["explicacao"], "tentativas": tentativa, "modelo": r.model}

        # o PostgreSQL recusou: devolve o erro ao modelo para ele corrigir
        # (a resposta volta inteira e sem alteração, com os blocos de raciocínio)
        mensagens += [
            {"role": "assistant", "content": r.content},
            {"role": "user", "content": f"O PostgreSQL recusou essa consulta com o erro:\n{erro}\nCorrija a consulta."},
        ]

    raise HTTPException(422, f"Não consegui montar uma consulta válida para essa pergunta. Último erro do banco: {erro}")
