# API da Santé: Ubuntu 26.04 LTS + Python 3.14 + FastAPI
FROM ubuntu:26.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=America/Maceio \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates tzdata postgresql-client \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv $VIRTUAL_ENV

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x scripts/*.sh \
 && useradd --create-home --uid 10001 sante \
 && chown -R sante:sante /app
USER sante

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/saude')"
ENTRYPOINT ["scripts/entrypoint.sh"]
