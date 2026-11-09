"""Carrega seed/sante.json, seed/concorrentes.json e seed/social.json no banco.

    python -m app.seed            # substitui tudo
    python -m app.seed --se-vazio # só carrega se o banco não tiver a clínica cadastrada
"""

import argparse
import asyncio
import json
from pathlib import Path

from tortoise import Tortoise
from tortoise.transactions import in_transaction

from app import models as m
from app import schemas as s
from app.db import TORTOISE_ORM
from app.services import documento

PASTA = Path(__file__).resolve().parent.parent / "seed"


def ler(nome: str) -> dict:
    return json.loads((PASTA / nome).read_text(encoding="utf-8"))


async def main(se_vazio: bool) -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    try:
        if se_vazio and await m.Clinica.exists():
            print("Seed: banco já tem dados, nada a fazer.")
            return
        # tudo ou nada: se um arquivo falhar, nenhum fica carregado pela metade
        async with in_transaction():
            total = await documento.importar(s.Documento.model_validate(ler("sante.json")))
            await documento.importar_concorrentes(ler("concorrentes.json"))
            await documento.importar_social(ler("social.json"))
        total["concorrentes"] = await m.Concorrente.all().count()
        total["postsSociais"] = await m.PostSocial.all().count()
        print("Seed carregado:", json.dumps(total, ensure_ascii=False))
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--se-vazio", action="store_true")
    asyncio.run(main(p.parse_args().se_vazio))
