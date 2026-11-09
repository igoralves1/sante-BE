from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from tortoise.contrib.fastapi import RegisterTortoise
from tortoise.exceptions import DoesNotExist, IntegrityError

from app.config import get_settings
from app.db import TORTOISE_ORM
from app.routers import cadastro, operacao, sistema


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with RegisterTortoise(app, config=TORTOISE_ORM):
        yield


app = FastAPI(
    title="Santé API",
    description="Backend do Santé Admin: espaços, turnos, agenda, contratos, locatários, custos e mercado.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_list,
    allow_origin_regex=get_settings().cors_origin_regex or None,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (sistema.router, cadastro.router, operacao.router):
    app.include_router(r, prefix="/api")


@app.exception_handler(DoesNotExist)
async def nao_existe(_: Request, exc: DoesNotExist):
    return JSONResponse(status_code=404, content={"detail": "Registro não encontrado."})


@app.exception_handler(IntegrityError)
async def conflito(_: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={"detail": f"Conflito com dados existentes: {exc}"})


@app.get("/", include_in_schema=False)
async def raiz():
    return {"api": "Santé API", "docs": "/docs", "saude": "/api/saude"}
