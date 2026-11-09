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

A documentação fica em http://localhost:8000/docs (Swagger) e http://localhost:8000/redoc (ReDoc).
Cada rota tem resumo, descrição, exemplos, o formato da resposta e os erros possíveis.
O front também mostra essa documentação, na página **Documentação da API**.

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
| `GET /api/banco/esquema` | Tabelas, colunas, chaves, índices e relações do banco (alimenta o diagrama do front) |
| `GET /api/banco/tabelas/{tabela}` | Linhas de uma tabela, com página, ordem e busca |
| `POST /api/banco/consulta` | Roda uma consulta SQL só de leitura |
| `POST /api/banco/traduzir` | Traduz uma pergunta em português para SQL, com o Claude (precisa de `ANTHROPIC_API_KEY`) |
| `GET /api/banco/assistente` | Diz se a tradução está disponível |
| `GET` e `PUT /api/banco/diagrama` | Posições das tabelas arrumadas à mão no diagrama do front |

Também há `GET` e `PUT /api/clinica`, para os dados da Santé e a meta de ocupação.

Os campos usam camelCase, iguais aos do front (`espacoId`, `precoTurno`...).

## Consultas ao banco (só leitura)

As rotas `/api/banco/*` alimentam as páginas **Diagrama do banco** e **Tabelas e consultas** do front.
Elas nunca usam a conexão principal da API:

- abrem conexões próprias com o papel `sante_leitura`, criado pela migração `papel_somente_leitura`, que só tem `SELECT` e não pode trocar de papel;
- a senha desse papel é aleatória e gerada a cada início da API (defina `BANCO_LEITURA_SENHA` se rodar vários workers);
- cada consulta roda numa transação `READ ONLY`, sempre termina em `ROLLBACK` e tem limite de tempo (`BANCO_TEMPO_MS`, 5 s por padrão);
- só um comando por vez, e no máximo 5.000 linhas na resposta.

Para desligar a navegação e as consultas (o esquema continua disponível), use `BANCO_CONSULTAS=false`.

## Perguntas em português (Claude)

A aba **Perguntar** do front transforma uma pergunta ("quanto cada sala faturou neste mês?") em SQL,
com o modelo `claude-opus-5-5` da Anthropic (`app/services/tradutor.py`).

- **Configurar:** crie uma chave em console.anthropic.com, coloque `ANTHROPIC_API_KEY=...` no `.env` e rode `docker compose up -d`.
- **O que sai do servidor:** só a pergunta, as perguntas anteriores da conversa com o SQL de cada uma, e a
  **estrutura** do banco (tabelas, colunas, tipos, relações e valores possíveis). Nenhuma linha de dado vai para a Anthropic.
- **Como funciona:** o modelo devolve o SQL e uma explicação; a API prepara a consulta no papel só de leitura
  (sem executar) e, se o PostgreSQL recusar, manda o erro de volta para o modelo corrigir (até 3 tentativas).
  O front roda o SQL em `POST /api/banco/consulta`.
- **Custo:** cada pergunta é uma chamada paga à API da Anthropic. O esquema fica em cache no prompt, o que
  barateia as perguntas seguintes. Os logs da API mostram os tokens de cada pergunta.

## Ligar o front

O [sante-admin](https://github.com/igoralves1/sante-admin) lê e grava todos os dados por esta API:

- **Endereço:** o front chama `/api` no mesmo endereço do site. No `npm run dev`, o Vite repassa `/api`,
  `/openapi.json`, `/docs` e `/redoc` para `http://localhost:8000`. Em produção (ECS/Fargate), o load balancer
  manda essas rotas para o container da API.
- **Como sincroniza:**
  - lê tudo em `GET /api/dados` e `GET /api/mercado/*`;
  - envia só o que mudou, pelas rotas de cada cadastro;
  - busca mudanças de outras pessoas a cada 20 segundos.
- **CORS:** com front e API no mesmo endereço, não é preciso. `CORS_ORIGINS` só serve se o front ficar em outro
  domínio; o front rodando na máquina (`localhost`, em qualquer porta) é sempre aceito.

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
