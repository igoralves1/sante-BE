from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "busca_mapa" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "busca" VARCHAR(200) NOT NULL,
    "posicao_sante" SMALLINT,
    "topo" TEXT[] NOT NULL,
    "ordem" SMALLINT NOT NULL
);
COMMENT ON TABLE "busca_mapa" IS 'Resultado de uma busca no Google Maps: posição da Santé e quem aparece no topo.';
CREATE TABLE IF NOT EXISTS "busca_youtube" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "termo" VARCHAR(200) NOT NULL,
    "analisados" INT NOT NULL,
    "do_setor" INT NOT NULL,
    "resumo" TEXT NOT NULL,
    "destaques" JSONB NOT NULL,
    "ordem" SMALLINT NOT NULL
);
CREATE TABLE IF NOT EXISTS "campanha" (
    "criado_em" TIMESTAMPTZ NOT NULL,
    "atualizado_em" TIMESTAMPTZ NOT NULL,
    "id" VARCHAR(40) NOT NULL PRIMARY KEY,
    "nome" VARCHAR(200) NOT NULL,
    "canal" VARCHAR(120) NOT NULL,
    "inicio" DATE,
    "fim" DATE,
    "orcamento" DECIMAL(12,2) NOT NULL,
    "leads" INT NOT NULL,
    "visitas" INT NOT NULL,
    "status" VARCHAR(20) NOT NULL,
    "obs" TEXT NOT NULL
);
COMMENT ON COLUMN "campanha"."status" IS 'PLANEJADA: Planejada\nATIVA: Ativa\nPAUSADA: Pausada\nCONCLUIDA: Concluída';
CREATE TABLE IF NOT EXISTS "clinica" (
    "criado_em" TIMESTAMPTZ NOT NULL,
    "atualizado_em" TIMESTAMPTZ NOT NULL,
    "id" SERIAL NOT NULL PRIMARY KEY,
    "nome" VARCHAR(120) NOT NULL,
    "razao_social" VARCHAR(160) NOT NULL,
    "endereco" VARCHAR(200) NOT NULL,
    "telefone" VARCHAR(30) NOT NULL,
    "whatsapp" VARCHAR(200) NOT NULL,
    "site" VARCHAR(200) NOT NULL,
    "instagram" VARCHAR(200) NOT NULL,
    "ocupacao_alvo" DECIMAL(5,4) NOT NULL,
    "impostos" DECIMAL(5,4) NOT NULL,
    "comissoes" DECIMAL(5,4) NOT NULL,
    "turnos_minimo" SMALLINT NOT NULL,
    "dados_atualizados_em" DATE
);
COMMENT ON TABLE "clinica" IS 'Dados da Santé e parâmetros gerais (uma linha só). No front: `meta`, `metas` e `custos`.';
CREATE TABLE IF NOT EXISTS "coleta" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "fonte" VARCHAR(30) NOT NULL UNIQUE,
    "coletado_em" DATE NOT NULL,
    "nota" TEXT NOT NULL
);
COMMENT ON TABLE "coleta" IS 'Data e nota de cada coleta manual (fonte = ''concorrentes'' ou ''social'').';
CREATE TABLE IF NOT EXISTS "concorrente" (
    "id" VARCHAR(40) NOT NULL PRIMARY KEY,
    "nome" VARCHAR(160) NOT NULL,
    "proprio" BOOL NOT NULL,
    "tipo" VARCHAR(30) NOT NULL,
    "local" VARCHAR(200) NOT NULL,
    "regiao" VARCHAR(80) NOT NULL,
    "modalidades" VARCHAR(200) NOT NULL,
    "preco" VARCHAR(300) NOT NULL,
    "horario" VARCHAR(200) NOT NULL,
    "diferenciais" TEXT NOT NULL,
    "reserva" VARCHAR(120) NOT NULL,
    "ameaca" VARCHAR(20),
    "site" VARCHAR(300) NOT NULL,
    "instagram" VARCHAR(120) NOT NULL,
    "ig" JSONB,
    "google" JSONB,
    "anuncios_meta" BOOL NOT NULL,
    "modalidades_n" SMALLINT,
    "preco_hora_min" INT,
    "horas_semana" INT,
    "ordem" SMALLINT NOT NULL
);
COMMENT ON TABLE "concorrente" IS 'Player do mercado de Maceió. proprio = True para a própria Santé.';
CREATE TABLE IF NOT EXISTS "avaliacao_site" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "site" VARCHAR(200) NOT NULL,
    "desempenho" SMALLINT,
    "acessibilidade" SMALLINT,
    "boas_praticas" SMALLINT,
    "seo" SMALLINT,
    "lcp" DECIMAL(6,2),
    "paginas" INT,
    "dominio" VARCHAR(20) NOT NULL,
    "obs" TEXT NOT NULL,
    "ordem" SMALLINT NOT NULL,
    "concorrente_id" VARCHAR(40) NOT NULL REFERENCES "concorrente" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "avaliacao_site" IS 'Notas do PageSpeed (Lighthouse) do site de um concorrente.';
CREATE TABLE IF NOT EXISTS "custo_fixo" (
    "id" VARCHAR(40) NOT NULL PRIMARY KEY,
    "descricao" VARCHAR(160) NOT NULL,
    "valor" DECIMAL(12,2) NOT NULL,
    "ordem" SMALLINT NOT NULL
);
COMMENT ON TABLE "custo_fixo" IS 'Custo fixo mensal da casa (aluguel, energia, recepção...).';
CREATE TABLE IF NOT EXISTS "espaco" (
    "criado_em" TIMESTAMPTZ NOT NULL,
    "atualizado_em" TIMESTAMPTZ NOT NULL,
    "id" VARCHAR(40) NOT NULL PRIMARY KEY,
    "nome" VARCHAR(80) NOT NULL UNIQUE,
    "tipo" VARCHAR(30) NOT NULL,
    "modalidade" VARCHAR(10) NOT NULL,
    "capacidade" DECIMAL(10,2) NOT NULL,
    "preco" DECIMAL(12,2) NOT NULL,
    "preco_turno" DECIMAL(12,2),
    "descricao" TEXT NOT NULL,
    "obs" TEXT NOT NULL,
    "turnos_proprios" BOOL NOT NULL,
    "agenda_minimo" SMALLINT,
    "ordem" SMALLINT NOT NULL
);
COMMENT ON COLUMN "espaco"."tipo" IS 'CONSULTORIO: Consultório\nPISCINA: Piscina\nADMINISTRATIVO: Administrativo\nPROCEDIMENTOS: Sala de procedimentos\nOUTRO: Outro';
COMMENT ON COLUMN "espaco"."modalidade" IS 'HORA: Hora\nTURNO: Turno\nMENSAL: Mensal';
COMMENT ON TABLE "espaco" IS 'Sala, piscina ou área administrativa que a Santé aluga (centro de custo).';
CREATE TABLE IF NOT EXISTS "despesa_espaco" (
    "id" VARCHAR(40) NOT NULL PRIMARY KEY,
    "descricao" VARCHAR(160) NOT NULL,
    "valor" DECIMAL(12,2) NOT NULL,
    "espaco_id" VARCHAR(40) NOT NULL REFERENCES "espaco" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "despesa_espaco" IS 'Despesa própria de um espaço (centro de custo).';
CREATE TABLE IF NOT EXISTS "preco_hora" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "label" VARCHAR(120) NOT NULL,
    "valor" DECIMAL(10,2) NOT NULL,
    "sub" VARCHAR(160) NOT NULL,
    "ordem" SMALLINT NOT NULL,
    "concorrente_id" VARCHAR(40) NOT NULL REFERENCES "concorrente" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "profissional" (
    "criado_em" TIMESTAMPTZ NOT NULL,
    "atualizado_em" TIMESTAMPTZ NOT NULL,
    "id" VARCHAR(40) NOT NULL PRIMARY KEY,
    "nome" VARCHAR(160) NOT NULL UNIQUE,
    "profissao" VARCHAR(80) NOT NULL,
    "especialidade" VARCHAR(120) NOT NULL,
    "registro" VARCHAR(40) NOT NULL,
    "ano_formatura" SMALLINT,
    "telefone" VARCHAR(30) NOT NULL,
    "email" VARCHAR(160) NOT NULL,
    "canal" VARCHAR(80) NOT NULL,
    "obs" TEXT NOT NULL
);
COMMENT ON TABLE "profissional" IS 'Locatário: profissional de saúde que aluga turnos ou salas.';
CREATE TABLE IF NOT EXISTS "agendamento" (
    "criado_em" TIMESTAMPTZ NOT NULL,
    "atualizado_em" TIMESTAMPTZ NOT NULL,
    "id" VARCHAR(40) NOT NULL PRIMARY KEY,
    "data" DATE NOT NULL,
    "slots" TEXT[] NOT NULL,
    "tipo" VARCHAR(10) NOT NULL,
    "cliente" VARCHAR(160) NOT NULL,
    "valor" DECIMAL(12,2) NOT NULL,
    "status" VARCHAR(20) NOT NULL,
    "obs" TEXT NOT NULL,
    "grupo" VARCHAR(40) NOT NULL,
    "espaco_id" VARCHAR(40) NOT NULL REFERENCES "espaco" ("id") ON DELETE CASCADE,
    "profissional_id" VARCHAR(40) REFERENCES "profissional" ("id") ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS "idx_agendamento_grupo_ba7db7" ON "agendamento" ("grupo");
CREATE INDEX IF NOT EXISTS "idx_agendamento_espaco__7827ca" ON "agendamento" ("espaco_id", "data");
COMMENT ON COLUMN "agendamento"."tipo" IS 'LOCACAO: locacao\nBLOQUEIO: bloqueio';
COMMENT ON COLUMN "agendamento"."status" IS 'CONFIRMADA: Confirmada\nPROPOSTA: Proposta\nCANCELADA: Cancelada';
COMMENT ON TABLE "agendamento" IS 'Turnos de um dia na agenda de um espaço: locação a um profissional ou \"Não disponível\".';
CREATE TABLE IF NOT EXISTS "contrato" (
    "criado_em" TIMESTAMPTZ NOT NULL,
    "atualizado_em" TIMESTAMPTZ NOT NULL,
    "id" VARCHAR(40) NOT NULL PRIMARY KEY,
    "cliente" VARCHAR(160) NOT NULL,
    "modalidade" VARCHAR(10) NOT NULL,
    "quantidade" DECIMAL(10,2) NOT NULL,
    "preco" DECIMAL(12,2) NOT NULL,
    "inicio" DATE NOT NULL,
    "fim" DATE,
    "status" VARCHAR(20) NOT NULL,
    "obs" TEXT NOT NULL,
    "campanha_id" VARCHAR(40) REFERENCES "campanha" ("id") ON DELETE SET NULL,
    "espaco_id" VARCHAR(40) NOT NULL REFERENCES "espaco" ("id") ON DELETE RESTRICT,
    "profissional_id" VARCHAR(40) REFERENCES "profissional" ("id") ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS "idx_contrato_espaco__6739af" ON "contrato" ("espaco_id", "inicio");
COMMENT ON COLUMN "contrato"."modalidade" IS 'HORA: Hora\nTURNO: Turno\nMENSAL: Mensal';
COMMENT ON COLUMN "contrato"."status" IS 'CONFIRMADA: Confirmada\nPROPOSTA: Proposta\nBASE_INICIAL: Base inicial\nCANCELADA: Cancelada';
COMMENT ON TABLE "contrato" IS 'Locação recorrente: quantidade de unidades (horas, turnos ou meses) por mês.';
CREATE TABLE IF NOT EXISTS "profissional_link" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "rede" VARCHAR(20) NOT NULL,
    "valor" VARCHAR(300) NOT NULL,
    "rotulo" VARCHAR(60) NOT NULL,
    "profissional_id" VARCHAR(40) NOT NULL REFERENCES "profissional" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "profissional_link" IS 'Rede social ou site do profissional. rede = instagram, linkedin, ... ou ''outra'' (com rótulo).';
CREATE TABLE IF NOT EXISTS "rede_social" (
    "id" VARCHAR(20) NOT NULL PRIMARY KEY,
    "nome" VARCHAR(40) NOT NULL,
    "contas_br" VARCHAR(40) NOT NULL,
    "fonte" VARCHAR(200) NOT NULL,
    "porque" TEXT NOT NULL,
    "ordem" SMALLINT NOT NULL
);
CREATE TABLE IF NOT EXISTS "perfil_social" (
    "id" VARCHAR(60) NOT NULL PRIMARY KEY,
    "handle" VARCHAR(120) NOT NULL,
    "nome" VARCHAR(160) NOT NULL,
    "seguidores" INT,
    "seguindo" INT,
    "publicacoes" INT,
    "checkins" INT,
    "falando_sobre" INT,
    "url" VARCHAR(300) NOT NULL,
    "status" VARCHAR(20) NOT NULL,
    "obs" TEXT NOT NULL,
    "ordem" SMALLINT NOT NULL,
    "concorrente_id" VARCHAR(40) NOT NULL REFERENCES "concorrente" ("id") ON DELETE CASCADE,
    "rede_id" VARCHAR(20) NOT NULL REFERENCES "rede_social" ("id") ON DELETE RESTRICT
);
COMMENT ON TABLE "perfil_social" IS 'Perfil de uma empresa numa rede. status: ativo, parado, nao-encontrado, perfil-pessoal.';
CREATE TABLE IF NOT EXISTS "post_social" (
    "id" VARCHAR(60) NOT NULL PRIMARY KEY,
    "data" DATE NOT NULL,
    "tipo" VARCHAR(10) NOT NULL,
    "curtidas" INT,
    "legenda" TEXT NOT NULL,
    "url" VARCHAR(300) NOT NULL,
    "perfil_id" VARCHAR(60) NOT NULL REFERENCES "perfil_social" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "trafego_site" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "site" VARCHAR(200) NOT NULL,
    "resultado" TEXT NOT NULL,
    "ordem" SMALLINT NOT NULL
);
COMMENT ON TABLE "trafego_site" IS 'Consulta de tráfego no Similarweb.';
CREATE TABLE IF NOT EXISTS "turno" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "nome" VARCHAR(30) NOT NULL,
    "ini" VARCHAR(5) NOT NULL,
    "fim" VARCHAR(5) NOT NULL,
    "dias" SMALLINT[] NOT NULL,
    "ordem" SMALLINT NOT NULL,
    "espaco_id" VARCHAR(40) REFERENCES "espaco" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "turno" IS 'Horário que pode ser locado. espaco nulo = turno da Santé, vale para todas as salas';
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS "campanha_espaco" (
    "campanha_id" VARCHAR(40) NOT NULL REFERENCES "campanha" ("id") ON DELETE CASCADE,
    "espaco_id" VARCHAR(40) NOT NULL REFERENCES "espaco" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "uidx_campanha_es_campanh_34932b" ON "campanha_espaco" ("campanha_id", "espaco_id");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
    "/x9Mzcvf"
)
