"""Base de dados: esquema (para o diagrama), navegação nas tabelas e consultas SQL só de leitura."""

import asyncio
import secrets
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, time as hora, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import asyncpg
from fastapi import APIRouter, HTTPException, Path, Query
from tortoise import connections
from tortoise.models import Model

from app import models as m
from app import schemas as s
from app.config import get_settings
from app.routers.comum import ERRO_400, ERRO_403, ERRO_404

router = APIRouter(prefix="/banco", tags=["base de dados"])

# grupos do diagrama (módulo do modelo no Tortoise)
GRUPOS = {"cadastro": "Cadastro", "operacao": "Operação", "mercado": "Mercado"}
TABELAS_EXTRAS = {
    "campanha_espaco": ("operacao", "Espaços de cada campanha (ligação muitos para muitos)."),
    "aerich": ("sistema", "Histórico das migrações aplicadas pelo Aerich."),
}
ACOES_FK = {"a": "NO ACTION", "r": "RESTRICT", "c": "CASCADE", "n": "SET NULL", "d": "SET DEFAULT"}


# ---------- conexão só de leitura ----------
# As consultas não usam a conexão principal (que, no Docker, é superusuário e poderia trocar de
# papel no meio de uma consulta). Elas abrem conexões próprias como sante_leitura, um papel que
# só tem SELECT e não pertence a nenhum outro. A senha é aleatória e gerada a cada início da API.
_pool: asyncpg.Pool | None = None
_trava = asyncio.Lock()


async def _abrir_pool() -> asyncpg.Pool:
    global _pool
    async with _trava:
        if _pool is None:
            cfg = get_settings()
            senha = cfg.banco_leitura_senha or secrets.token_hex(24)
            async with connections.get("default").acquire_connection() as con:
                literal = "'" + senha.replace("'", "''") + "'"
                await con.execute(f"ALTER ROLE sante_leitura WITH LOGIN PASSWORD {literal}")
            url = urlsplit(cfg.database_url)
            _pool = await asyncpg.create_pool(
                host=url.hostname, port=url.port or 5432, database=url.path.lstrip("/"),
                user="sante_leitura", password=senha, min_size=0, max_size=3,
                server_settings={"application_name": "sante-consultas"},
            )
    return _pool


async def fechar() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def somente_leitura():
    """Transação read-only como sante_leitura, com tempo máximo. Sempre termina em rollback."""
    async with (await _abrir_pool()).acquire() as con:
        tr = con.transaction(readonly=True)
        await tr.start()
        try:
            await con.execute(f"SET LOCAL statement_timeout = {int(get_settings().banco_tempo_ms)}")
            yield con
        finally:
            await tr.rollback()


def _exigir_consultas() -> None:
    if not get_settings().banco_consultas:
        raise HTTPException(403, "As consultas ao banco estão desligadas neste servidor (BANCO_CONSULTAS=false).")


def _erro_sql(e: Exception) -> HTTPException:
    msg = str(e)
    if isinstance(e, asyncpg.exceptions.QueryCanceledError):
        msg = f"A consulta passou de {get_settings().banco_tempo_ms / 1000:g} s e foi cancelada."
    elif isinstance(e, asyncpg.exceptions.ReadOnlySQLTransactionError):
        msg = f"Só consultas de leitura são permitidas aqui ({msg})."
    elif isinstance(e, asyncpg.exceptions.InsufficientPrivilegeError):
        msg = f"Sem permissão nesta ferramenta, que só lê as tabelas do sistema ({msg})."
    elif "multiple commands" in msg:
        msg = "Envie um comando por vez."
    elif isinstance(e, asyncpg.exceptions.PostgresSyntaxError):
        msg = f"Erro de sintaxe: {msg}"
    return HTTPException(400, msg)


def valor(v: Any) -> Any:
    """Converte um valor do Postgres para JSON sem perder informação."""
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, (datetime, date, hora)):
        return v.isoformat()
    if isinstance(v, (UUID, timedelta)):
        return str(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        return "\\x" + bytes(v).hex()
    if isinstance(v, (list, tuple)):
        return [valor(x) for x in v]
    if isinstance(v, dict):
        return {k: valor(x) for k, x in v.items()}
    return str(v)


def _q(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


# ---------- esquema ----------
def _descricoes() -> dict[str, tuple[str, str]]:
    """tabela -> (grupo, descrição), a partir dos modelos do Tortoise."""
    out = dict(TABELAS_EXTRAS)
    for nome in dir(m):
        modelo = getattr(m, nome)
        if not (isinstance(modelo, type) and issubclass(modelo, Model)) or modelo._meta.abstract:
            continue
        tabela = modelo._meta.db_table
        grupo = modelo.__module__.rsplit(".", 1)[-1]
        doc = " ".join((modelo.__doc__ or "").split())
        out[tabela] = (grupo, doc)
    return out


SQL_COLUNAS = """
SELECT c.relname AS tabela, a.attname AS coluna, a.attnum AS posicao,
       format_type(a.atttypid, a.atttypmod) AS tipo, NOT a.attnotnull AS nulo,
       pg_get_expr(d.adbin, d.adrelid) AS padrao
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
WHERE n.nspname = 'public' AND c.relkind = 'r' AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY c.relname, a.attnum
"""

SQL_RESTRICOES = """
SELECT con.conname AS nome, con.contype::text AS tipo, cl.relname AS tabela,
       ARRAY(SELECT a.attname FROM unnest(con.conkey) WITH ORDINALITY k(n, o)
             JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.n ORDER BY k.o) AS colunas,
       fcl.relname AS ref_tabela,
       ARRAY(SELECT a.attname FROM unnest(con.confkey) WITH ORDINALITY k(n, o)
             JOIN pg_attribute a ON a.attrelid = con.confrelid AND a.attnum = k.n ORDER BY k.o) AS ref_colunas,
       con.confdeltype::text AS ao_excluir
FROM pg_constraint con
JOIN pg_class cl ON cl.oid = con.conrelid
JOIN pg_namespace n ON n.oid = cl.relnamespace
LEFT JOIN pg_class fcl ON fcl.oid = con.confrelid
WHERE n.nspname = 'public' AND con.contype IN ('p', 'f', 'u')
ORDER BY cl.relname, con.conname
"""

SQL_INDICES = """
SELECT tablename AS tabela, indexname AS nome, indexdef AS definicao
FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname
"""


async def _tabelas(con: asyncpg.Connection) -> list[str]:
    linhas = await con.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    )
    return [r["tablename"] for r in linhas]


async def ler_esquema() -> dict:
    async with somente_leitura() as con:
        nomes = await _tabelas(con)
        colunas = await con.fetch(SQL_COLUNAS)
        restricoes = await con.fetch(SQL_RESTRICOES)
        indices = await con.fetch(SQL_INDICES)
        contagens = {t: await con.fetchval(f"SELECT count(*) FROM {_q(t)}") for t in nomes}
        versao = await con.fetchval("SHOW server_version")

    desc = _descricoes()
    tabelas: dict[str, dict] = {
        t: {
            "nome": t,
            "grupo": desc.get(t, ("outros", ""))[0],
            "descricao": desc.get(t, ("", ""))[1],
            "linhas": contagens[t],
            "colunas": [],
            "chavePrimaria": [],
            "unicas": [],
            "indices": [],
        }
        for t in nomes
    }
    for c in colunas:
        tabelas[c["tabela"]]["colunas"].append(
            {"nome": c["coluna"], "tipo": c["tipo"], "nulo": c["nulo"], "padrao": c["padrao"], "pk": False, "fk": None}
        )
    relacoes = []
    for r in restricoes:
        t = tabelas.get(r["tabela"])
        if t is None:
            continue
        cols = list(r["colunas"])
        if r["tipo"] == "p":
            t["chavePrimaria"] = cols
            for col in t["colunas"]:
                col["pk"] = col["nome"] in cols
        elif r["tipo"] == "u":
            t["unicas"].append(cols)
        elif r["tipo"] == "f":
            ref = {"tabela": r["ref_tabela"], "colunas": list(r["ref_colunas"]), "aoExcluir": ACOES_FK.get(r["ao_excluir"], "")}
            for col in t["colunas"]:
                if col["nome"] in cols:
                    col["fk"] = {"tabela": ref["tabela"], "coluna": ref["colunas"][cols.index(col["nome"])]}
            relacoes.append({"nome": r["nome"], "de": r["tabela"], "colunas": cols, "para": ref["tabela"],
                             "refColunas": ref["colunas"], "aoExcluir": ref["aoExcluir"]})
    for i in indices:
        if i["tabela"] in tabelas:
            tabelas[i["tabela"]]["indices"].append({"nome": i["nome"], "definicao": i["definicao"]})

    return {
        "banco": f"PostgreSQL {versao}",
        "geradoEm": datetime.now().astimezone().isoformat(timespec="seconds"),
        "grupos": {**GRUPOS, "sistema": "Sistema"},
        "tabelas": list(tabelas.values()),
        "relacoes": relacoes,
    }


@router.get(
    "/esquema",
    summary="Esquema do banco (tabelas, colunas, chaves e relações)",
    response_model=s.Esquema,
)
async def esquema():
    """Lê o catálogo do PostgreSQL e devolve cada tabela com colunas, tipos, chave primária,
    restrições únicas, índices, número de linhas e as chaves estrangeiras entre tabelas.

    Alimenta a página **Base de dados → Diagrama do banco**. O grupo e a descrição de cada tabela
    vêm dos modelos do Tortoise (`app/models`)."""
    return await ler_esquema()


# ---------- navegar nas tabelas ----------
@router.get(
    "/tabelas/{tabela}",
    summary="Linhas de uma tabela, com página, ordem e busca",
    response_model=s.Resultado,
    responses={**ERRO_400, **ERRO_403, **ERRO_404},
)
async def linhas(
    tabela: str = Path(description="Nome da tabela, como aparece em `/api/banco/esquema`.", examples=["espaco"]),
    limite: int = Query(50, ge=1, le=1000, description="Linhas por página."),
    pagina: int = Query(1, ge=1, description="Página, começando em 1."),
    ordem: str | None = Query(None, description="Coluna para ordenar. Sem ela, usa a chave primária."),
    desc: bool = Query(False, description="Ordem decrescente."),
    busca: str | None = Query(None, description="Texto procurado em qualquer coluna (sem diferenciar maiúsculas)."),
):
    """Mostra as linhas de uma tabela, como uma planilha. A busca compara o texto com a linha
    inteira convertida em texto, então encontra o valor em qualquer coluna.

    Roda numa transação só de leitura, com o papel `sante_leitura`."""
    _exigir_consultas()
    inicio = time.perf_counter()
    try:
        async with somente_leitura() as con:
            if tabela not in await _tabelas(con):
                raise HTTPException(404, f"Tabela {tabela} não existe.")
            info = await con.fetch(
                "SELECT a.attname, format_type(a.atttypid, a.atttypmod) AS tipo FROM pg_attribute a "
                "WHERE a.attrelid = $1::regclass AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum",
                _q(tabela),
            )
            nomes = [r["attname"] for r in info]
            if ordem and ordem not in nomes:
                raise HTTPException(400, f"A tabela {tabela} não tem a coluna {ordem}.")
            if not ordem:
                pk = await con.fetch(
                    "SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid "
                    "AND a.attnum = ANY(i.indkey) WHERE i.indrelid = $1::regclass AND i.indisprimary",
                    _q(tabela),
                )
                ordem = pk[0]["attname"] if pk else nomes[0]
            onde, args = "", []
            if busca:
                onde, args = "WHERE t::text ILIKE $1", [f"%{busca}%"]
            total = await con.fetchval(f"SELECT count(*) FROM {_q(tabela)} t {onde}", *args)
            n = len(args)
            dados = await con.fetch(
                f"SELECT * FROM {_q(tabela)} t {onde} ORDER BY {_q(ordem)} {'DESC' if desc else 'ASC'} NULLS LAST "
                f"LIMIT ${n + 1} OFFSET ${n + 2}",
                *args, limite, (pagina - 1) * limite,
            )
    except asyncpg.PostgresError as e:
        raise _erro_sql(e) from None
    return {
        "colunas": [{"nome": r["attname"], "tipo": r["tipo"]} for r in info],
        "linhas": [[valor(v) for v in r.values()] for r in dados],
        "quantidade": len(dados),
        "total": total,
        "truncado": pagina * limite < total,
        "tempoMs": round((time.perf_counter() - inicio) * 1000, 1),
        "comando": "SELECT",
    }


# ---------- consultas SQL ----------
@router.post(
    "/consulta",
    summary="Roda uma consulta SQL só de leitura",
    response_model=s.Resultado,
    responses={**ERRO_400, **ERRO_403},
)
async def consulta(dados: s.Consulta):
    """Executa **um** comando SQL e devolve as colunas e as linhas.

    Proteções:

    - roda numa transação `READ ONLY` com o papel `sante_leitura`, que só tem `SELECT`;
      `INSERT`, `UPDATE`, `DELETE`, `CREATE`... são recusados pelo próprio PostgreSQL;
    - a transação sempre termina em `ROLLBACK`;
    - um comando por vez (o comando é preparado, e o PostgreSQL recusa vários);
    - tempo máximo de `BANCO_TEMPO_MS` (5 s por padrão);
    - no máximo `limite` linhas voltam; `truncado` diz se havia mais.

    Aceita `SELECT`, `WITH`, `EXPLAIN`, `SHOW` e `VALUES`."""
    _exigir_consultas()
    sql = dados.sql.strip().rstrip(";").strip()
    if not sql:
        raise HTTPException(400, "Escreva uma consulta.")
    inicio = time.perf_counter()
    try:
        async with somente_leitura() as con:
            stmt = await con.prepare(sql)
            colunas = [{"nome": a.name, "tipo": a.type.name} for a in stmt.get_attributes()]
            if colunas:
                cursor = await stmt.cursor()
                dados_ = await cursor.fetch(dados.limite + 1)
            else:
                await stmt.fetch()
                dados_ = []
    except asyncpg.PostgresError as e:
        raise _erro_sql(e) from None
    truncado = len(dados_) > dados.limite
    dados_ = dados_[: dados.limite]
    return {
        "colunas": colunas,
        "linhas": [[valor(v) for v in r.values()] for r in dados_],
        "quantidade": len(dados_),
        "total": None,
        "truncado": truncado,
        "tempoMs": round((time.perf_counter() - inicio) * 1000, 1),
        "comando": sql.split(None, 1)[0].upper(),
    }
