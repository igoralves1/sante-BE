# sante-BE

Backend do [Santé Admin](https://github.com/igoralves1/sante-admin). O front hoje lê o `sante.json` e guarda as edições só no navegador. Esta API passa a guardar os dados num banco PostgreSQL compartilhado.

- **Servidor:** Ubuntu 26.04 LTS, Python 3.14.
- **API:** FastAPI.
- **Banco:** Tortoise ORM com migrações do Aerich, em PostgreSQL 18.
- **Modelo de dados:** 21 tabelas, que cobrem espaços, turnos, agenda, contratos, locatários, custos, campanhas, concorrentes e o monitor social. Detalhes em [docs/MODELO.md](docs/MODELO.md).

## Rodar localmente

Precisa do Docker Desktop.

```bash
cp .env.example .env
docker compose up -d --build
```

Ao subir, o container da API:

1. espera o Postgres;
2. aplica as migrações (`aerich upgrade`);
3. carrega os arquivos de `seed/` se o banco estiver vazio;
4. sobe a API em http://localhost:8000.

A documentação interativa fica em http://localhost:8000/docs.

No compose de desenvolvimento, a pasta `app/` entra no container e a API recarrega a cada alteração.

| Comando | Para quê |
|---|---|
| `docker compose logs -f api` | Ver os logs da API |
| `docker compose exec api python -m app.seed` | Recarregar o seed (substitui os dados) |
| `docker compose exec api aerich migrate --name x` | Gerar migração depois de mudar um modelo |
| `docker compose exec api aerich upgrade` | Aplicar migrações |
| `docker compose exec db psql -U sante` | Abrir o banco |
| `docker compose down` | Parar (os dados ficam no volume `pgdata`) |
| `docker compose down -v` | Parar e apagar o banco |

## Rotas

| Rota | O que faz |
|---|---|
| `GET /api/saude` | A API e o banco estão no ar? |
| `GET` e `PUT /api/dados` | Tudo no formato do `sante.json`. O `PUT` substitui tudo, numa transação só. |
| `GET` e `PUT /api/turnos` | Turnos da Santé |
| `/api/espacos` (+ `/{id}`) | Espaços, com despesas e turnos próprios |
| `GET /api/espacos/{id}/capacidade?mes=2026-11` | Turnos do mês: no calendário, não disponíveis, em aberto, ocupados, livres e receita não realizada |
| `GET /api/capacidade?mes=2026-11` | O mesmo para todos os espaços |
| `/api/agendamentos` (+ `/lote`, `/grupo/{grupo}`) | Agenda: locações e turnos "Não disponível". Recusa conflitos e turnos que a sala não abre. |
| `/api/contratos`, `/api/profissionais`, `/api/campanhas` | Cadastro completo (listar, criar, editar, excluir) |
| `GET` e `PUT /api/custos` | Custos fixos, impostos e comissões |
| `GET` e `PUT /api/mercado/concorrentes`, `/api/mercado/social` | Coletas de mercado, no formato dos arquivos do front |

Os campos usam camelCase, iguais aos do front (`espacoId`, `precoTurno`...). O front pode trocar a leitura do `sante.json` por `GET /api/dados` sem mudar o resto.

## Estrutura

```
app/
  models/      modelos do Tortoise (cadastro, operação, mercado)
  routers/     rotas da API
  services/    cálculo de turnos, importação e exportação do sante.json
  schemas.py   validação de entrada (Pydantic)
  seed.py      carga dos arquivos de seed/
migrations/    migrações do Aerich (versionadas)
seed/          cópia dos JSON do front usada na carga inicial
```

## Dados pessoais (LGPD)

O seed só tem dados da empresa e páginas públicas de concorrentes. Locatários (nome, telefone, e-mail, redes) passam a ficar só no banco. Para não expor esses dados:

- nunca os coloque em `seed/` nem em commits;
- não suba o arquivo `.env`;
- antes de publicar a API, troque a senha padrão do Postgres e adicione login.
