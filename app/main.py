from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from tortoise.contrib.fastapi import RegisterTortoise
from tortoise.exceptions import DoesNotExist, IntegrityError

from app.config import get_settings
from app.db import TORTOISE_ORM
from app.routers import banco, cadastro, operacao, sistema

DESCRICAO = """
Backend do **Santé Admin**, o sistema de gestão da Santé Consultórios (Maceió).
Guarda num PostgreSQL os espaços, os turnos, a agenda, os contratos, os locatários, os custos,
as campanhas e as coletas de mercado.

## Como usar

- Todas as rotas ficam em `/api`.
- Os campos usam **camelCase**, iguais aos do `sante.json` do front (`espacoId`, `precoTurno`...).
- Na entrada, texto vazio (`""`) em datas e números opcionais vale como "sem valor".
- Datas no formato `AAAA-MM-DD`, meses no formato `AAAA-MM` e turnos no formato `HH:MM-HH:MM`.
- IDs são textos (`e1`, `ct1`, `ag3f9a1c2b`...). Na criação, sem `id`, a API gera um.

## Como o front usa a API

1. Lê tudo em `GET /api/dados`.
2. A cada alteração na tela, envia só o que mudou, pelas rotas de cada cadastro
   (criar, editar ou excluir), na ordem que o banco exige.
3. A cada 20 segundos, e ao voltar para a aba, lê `GET /api/dados` de novo para ver mudanças de outras pessoas.
4. Se o servidor recusar algo, a tela mostra o motivo e volta ao que está gravado.

## Capacidade dos espaços

- **No calendário:** turnos que abrem em cada dia do mês.
- **Não disponíveis:** turnos bloqueados na agenda.
- **Em aberto:** no calendário − não disponíveis. É a capacidade real do mês.
- **Ocupados:** turnos locados. **Livres:** em aberto − ocupados.

Espaços cobrados por hora contam horas. Espaços `Mensal` e `Administrativo` não usam agenda.

## Erros

Todo erro responde com `{"detail": "..."}`, uma frase em português pronta para mostrar na tela.
Na validação automática dos campos, `detail` é a lista dos campos com erro.

| Código | Quando |
|---|---|
| 400 | Pedido inválido (ex.: SQL com erro) |
| 403 | Recurso desligado neste servidor |
| 404 | Registro não encontrado |
| 409 | Conflito: nome repetido, turno já ocupado, espaço com contratos |
| 422 | Dados inválidos ou fora das regras (turno fechado no dia, término antes do início...) |

## Segurança e LGPD

A API ainda **não tem login**: use só na sua máquina ou numa rede fechada. Os locatários têm dados
pessoais (nome, telefone, e-mail, redes). Antes de publicar a API, troque a senha do banco e adicione login.
"""

TAGS = [
    {"name": "documento", "description": "O sistema inteiro num documento só, no formato do `sante.json`. Leitura, backup e importação."},
    {"name": "clínica", "description": "Dados da Santé (contatos, site, Instagram) e a meta de ocupação."},
    {"name": "turnos", "description": "Turnos da Santé. Valem para todas as salas que não têm turnos próprios."},
    {"name": "espaços", "description": "Salas, piscina e áreas (centros de custo), com despesas, turnos próprios e a capacidade do mês."},
    {"name": "agenda", "description": "Turnos locados e turnos \"Não disponível\", dia a dia. Recusa conflitos e turnos que o espaço não abre."},
    {"name": "contratos", "description": "Carteira de contratos: locações recorrentes (horas, turnos ou meses por mês)."},
    {"name": "locatários", "description": "Profissionais de saúde que alugam turnos ou salas. **Contém dados pessoais.**"},
    {"name": "custos", "description": "Custos fixos mensais e os percentuais de impostos e comissões."},
    {"name": "campanhas", "description": "Ações comerciais e seus resultados."},
    {"name": "mercado", "description": "Concorrentes e monitor social: coletas manuais de páginas públicas."},
    {
        "name": "base de dados",
        "description": "Esquema do banco, navegação nas tabelas e consultas SQL **só de leitura**. "
        "Tudo roda numa transação read-only com o papel `sante_leitura`, que só tem `SELECT`. "
        "Desligue com `BANCO_CONSULTAS=false`.",
    },
    {"name": "sistema", "description": "Saúde da API."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with RegisterTortoise(app, config=TORTOISE_ORM):
        yield
        await banco.fechar()


app = FastAPI(
    title="Santé API",
    summary="Espaços, turnos, agenda, contratos, locatários, custos e mercado da Santé Consultórios.",
    description=DESCRICAO,
    version="0.2.0",
    openapi_tags=TAGS,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    contact={"name": "Santé Consultórios", "url": "https://github.com/igoralves1/sante-admin"},
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_list,
    allow_origin_regex=get_settings().cors_origin_regex or None,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (sistema.router, cadastro.router, operacao.router, banco.router):
    app.include_router(r, prefix="/api")


@app.exception_handler(DoesNotExist)
async def nao_existe(_: Request, exc: DoesNotExist):
    return JSONResponse(status_code=404, content={"detail": "Registro não encontrado."})


@app.exception_handler(IntegrityError)
async def conflito(_: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={"detail": f"Conflito com dados existentes: {exc}"})


@app.get("/", include_in_schema=False)
async def raiz():
    return {"api": "Santé API", "docs": "/docs", "redoc": "/redoc", "openapi": "/openapi.json", "saude": "/api/saude"}
