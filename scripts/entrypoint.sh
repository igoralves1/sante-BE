#!/bin/sh
# Espera o Postgres, aplica as migrações do Aerich, carrega o seed (se o banco estiver vazio) e sobe a API.
set -e

until pg_isready -q -d "$DATABASE_URL"; do
  echo "Aguardando o Postgres..."
  sleep 1
done

aerich upgrade

if [ "${SEED_ON_START:-true}" = "true" ]; then
  python -m app.seed --se-vazio
fi

if [ "${RELOAD:-false}" = "true" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
