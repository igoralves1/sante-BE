"""Importa e exporta o documento inteiro no formato do front:
sante.json (dados da casa), social.json (monitor social) e concorrentes.json."""

from datetime import date

from tortoise.transactions import in_transaction

from app import models as m
from app import schemas as s
from app.services import gravar
from app.services import serializar as ser


# ---------- sante.json ----------
async def exportar() -> dict:
    c = await m.Clinica.first()
    if c is None:
        return {}
    espacos = await m.Espaco.all().prefetch_related("turnos", "despesas")
    centrais = await m.Turno.filter(espaco_id__isnull=True)
    return {
        "meta": {
            "versao": 2,
            "clinica": c.nome,
            "razaoSocial": c.razao_social,
            "endereco": c.endereco,
            "telefone": c.telefone,
            "whatsapp": c.whatsapp,
            "site": c.site,
            "instagram": c.instagram,
            "atualizadoEm": ser.iso(c.dados_atualizados_em),
        },
        "metas": {"ocupacaoAlvo": ser.num(c.ocupacao_alvo)},
        "turnos": ser.agenda(centrais, c.turnos_minimo),
        "espacos": [ser.espaco(e) for e in espacos],
        "custos": {
            "fixos": [ser.custo(x) for x in await m.CustoFixo.all()],
            "impostos": ser.num(c.impostos),
            "comissoes": ser.num(c.comissoes),
        },
        "campanhas": [ser.campanha(x) for x in await m.Campanha.all().prefetch_related("espacos")],
        "contratos": [ser.contrato(x) for x in await m.Contrato.all().order_by("inicio", "id")],
        "agendamentos": [ser.agendamento(x) for x in await m.Agendamento.all().order_by("data", "id")],
        "profissionais": [ser.profissional(x) for x in await m.Profissional.all().prefetch_related("links")],
    }


async def importar(doc: s.Documento) -> dict:
    """Substitui todos os dados da casa pelo documento (tudo ou nada)."""
    async with in_transaction():
        for modelo in (m.Agendamento, m.Contrato, m.Campanha, m.Turno, m.DespesaEspaco, m.Espaco,
                       m.CustoFixo, m.ProfissionalLink, m.Profissional, m.Clinica):
            await modelo.all().delete()

        await m.Clinica.create(
            nome=doc.meta.clinica,
            razao_social=doc.meta.razao_social,
            endereco=doc.meta.endereco,
            telefone=doc.meta.telefone,
            whatsapp=doc.meta.whatsapp,
            site=doc.meta.site,
            instagram=doc.meta.instagram,
            dados_atualizados_em=doc.meta.atualizado_em,
            ocupacao_alvo=doc.metas.ocupacao_alvo,
            impostos=doc.custos.impostos,
            comissoes=doc.custos.comissoes,
            turnos_minimo=doc.turnos.minimo,
        )
        await gravar.gravar_turnos(doc.turnos.horarios)
        for i, e in enumerate(doc.espacos):
            await gravar.gravar_espaco(e, ordem=i)
        await gravar.gravar_custos(doc.custos)
        for p in doc.profissionais:
            await gravar.gravar_profissional(p)
        for c in doc.campanhas:
            await gravar.gravar_campanha(c)
        for c in doc.contratos:
            await gravar.gravar_contrato(c)
        await m.Agendamento.bulk_create(
            [m.Agendamento(id=a.id or ser.uid("ag"), **a.model_dump(exclude={"id"})) for a in doc.agendamentos]
        )
    return await contagem()


async def contagem() -> dict:
    return {
        "espacos": await m.Espaco.all().count(),
        "turnos": await m.Turno.all().count(),
        "contratos": await m.Contrato.all().count(),
        "agendamentos": await m.Agendamento.all().count(),
        "profissionais": await m.Profissional.all().count(),
        "campanhas": await m.Campanha.all().count(),
        "custosFixos": await m.CustoFixo.all().count(),
    }


# ---------- concorrentes.json ----------
def _data(v: str | None) -> date | None:
    return date.fromisoformat(v) if v else None


async def importar_concorrentes(doc: dict) -> None:
    async with in_transaction():
        for modelo in (m.PrecoHora, m.BuscaMapa, m.AvaliacaoSite, m.TrafegoSite):
            await modelo.all().delete()
        await m.Coleta.update_or_create(
            fonte="concorrentes", defaults={"coletado_em": _data(doc["coletadoEm"]), "nota": (doc.get("nota") or "")}
        )
        for i, p in enumerate(doc.get("players", [])):
            await m.Concorrente.update_or_create(
                id=p["id"],
                defaults={
                    "nome": p["nome"],
                    "proprio": bool(p.get("proprio")),
                    "tipo": (p.get("tipo") or ""),
                    "local": (p.get("local") or ""),
                    "regiao": (p.get("regiao") or ""),
                    "modalidades": (p.get("modalidades") or ""),
                    "preco": (p.get("preco") or ""),
                    "horario": (p.get("horario") or ""),
                    "diferenciais": (p.get("diferenciais") or ""),
                    "reserva": (p.get("reserva") or ""),
                    "ameaca": p.get("ameaca"),
                    "site": (p.get("site") or ""),
                    "instagram": (p.get("instagram") or ""),
                    "ig": p.get("ig"),
                    "google": p.get("google"),
                    "anuncios_meta": bool(p.get("anunciosMeta")),
                    "modalidades_n": p.get("modalidadesN"),
                    "preco_hora_min": p.get("precoHoraMin"),
                    "horas_semana": p.get("horasSemana"),
                    "ordem": i,
                },
            )
        await m.PrecoHora.bulk_create(
            [m.PrecoHora(concorrente_id=x["id"], label=x["label"], valor=x["valor"], sub=(x.get("sub") or ""), ordem=i)
             for i, x in enumerate(doc.get("precoHora", []))]
        )
        await m.BuscaMapa.bulk_create(
            [m.BuscaMapa(busca=x["busca"], posicao_sante=x.get("sante"), topo=x.get("topo", []), ordem=i)
             for i, x in enumerate(doc.get("mapas", []))]
        )
        await m.AvaliacaoSite.bulk_create(
            [m.AvaliacaoSite(concorrente_id=x["id"], site=x["site"], desempenho=x.get("desempenho"),
                             acessibilidade=x.get("acessibilidade"), boas_praticas=x.get("boasPraticas"),
                             seo=x.get("seo"), lcp=x.get("lcp"), paginas=x.get("paginas"),
                             dominio=(x.get("dominio") or ""), obs=(x.get("obs") or ""), ordem=i)
             for i, x in enumerate(doc.get("sites", []))]
        )
        await m.TrafegoSite.bulk_create(
            [m.TrafegoSite(site=x["site"], resultado=(x.get("resultado") or ""), ordem=i)
             for i, x in enumerate(doc.get("similarweb", []))]
        )


async def exportar_concorrentes() -> dict:
    coleta = await m.Coleta.get_or_none(fonte="concorrentes")
    players = []
    for p in await m.Concorrente.all():
        players.append({
            "id": p.id, "nome": p.nome, "proprio": p.proprio, "tipo": p.tipo, "local": p.local,
            "regiao": p.regiao, "modalidades": p.modalidades, "preco": p.preco, "horario": p.horario,
            "diferenciais": p.diferenciais, "reserva": p.reserva, "ameaca": p.ameaca, "site": p.site,
            "instagram": p.instagram, "ig": p.ig, "google": p.google, "anunciosMeta": p.anuncios_meta,
            "modalidadesN": p.modalidades_n, "precoHoraMin": p.preco_hora_min, "horasSemana": p.horas_semana,
        })
    return {
        "coletadoEm": ser.iso(coleta.coletado_em) if coleta else "",
        "nota": coleta.nota if coleta else "",
        "players": players,
        "precoHora": [{"id": x.concorrente_id, "label": x.label, "valor": ser.num(x.valor), "sub": x.sub}
                      for x in await m.PrecoHora.all()],
        "mapas": [{"busca": x.busca, "sante": x.posicao_sante, "topo": list(x.topo)} for x in await m.BuscaMapa.all()],
        "sites": [{"id": x.concorrente_id, "site": x.site, "desempenho": x.desempenho,
                   "acessibilidade": x.acessibilidade, "boasPraticas": x.boas_praticas, "seo": x.seo,
                   "lcp": ser.num(x.lcp), "paginas": x.paginas, "dominio": x.dominio, "obs": x.obs}
                  for x in await m.AvaliacaoSite.all()],
        "similarweb": [{"site": x.site, "resultado": x.resultado} for x in await m.TrafegoSite.all()],
    }


# ---------- social.json ----------
async def importar_social(doc: dict) -> None:
    async with in_transaction():
        await m.PostSocial.all().delete()
        await m.PerfilSocial.all().delete()
        await m.BuscaYoutube.all().delete()
        await m.Coleta.update_or_create(
            fonte="social", defaults={"coletado_em": _data(doc["coletadoEm"]), "nota": (doc.get("nota") or "")}
        )
        for i, r in enumerate(doc.get("redes", [])):
            await m.RedeSocial.update_or_create(
                id=r["id"],
                defaults={"nome": r["nome"], "contas_br": (r.get("contasBR") or ""), "fonte": (r.get("fonte") or ""),
                          "porque": (r.get("porque") or ""), "ordem": i},
            )
        for p in doc.get("perfis", []):
            # a empresa precisa existir no cadastro de concorrentes
            await m.Concorrente.get_or_create(id=p["empresa"], defaults={"nome": p.get("nome") or p["empresa"]})
        await m.PerfilSocial.bulk_create(
            [m.PerfilSocial(id=p["id"], concorrente_id=p["empresa"], rede_id=p["rede"], handle=(p.get("handle") or ""),
                            nome=(p.get("nome") or ""), seguidores=p.get("seguidores"), seguindo=p.get("seguindo"),
                            publicacoes=p.get("publicacoes"), checkins=p.get("checkins"),
                            falando_sobre=p.get("falandoSobre"), url=(p.get("url") or ""),
                            status=p.get("status", "ativo"), obs=(p.get("obs") or ""), ordem=i)
             for i, p in enumerate(doc.get("perfis", []))]
        )
        await m.PostSocial.bulk_create(
            [m.PostSocial(id=x["id"], perfil_id=x["perfil"], data=_data(x["data"]), tipo=x["tipo"],
                          curtidas=x.get("curtidas"), legenda=(x.get("legenda") or ""), url=(x.get("url") or ""), ordem=i)
             for i, x in enumerate(doc.get("posts", []))]
        )
        await m.BuscaYoutube.bulk_create(
            [m.BuscaYoutube(termo=x["termo"], analisados=x.get("analisados", 0), do_setor=x.get("doSetor", 0),
                            resumo=(x.get("resumo") or ""), destaques=x.get("destaques", []), ordem=i)
             for i, x in enumerate(doc.get("buscasYoutube", []))]
        )


async def exportar_social() -> dict:
    coleta = await m.Coleta.get_or_none(fonte="social")
    redes = []
    for r in await m.RedeSocial.all():
        x = {"id": r.id, "nome": r.nome, "contasBR": r.contas_br, "fonte": r.fonte}
        if r.porque:
            x["porque"] = r.porque
        redes.append(x)
    perfis = []
    for p in await m.PerfilSocial.all():
        x = {"id": p.id, "empresa": p.concorrente_id, "rede": p.rede_id, "handle": p.handle, "nome": p.nome,
             "seguidores": p.seguidores, "seguindo": p.seguindo, "publicacoes": p.publicacoes,
             "checkins": p.checkins, "falandoSobre": p.falando_sobre, "url": p.url, "status": p.status, "obs": p.obs}
        perfis.append({k: v for k, v in x.items() if v not in (None, "")})
    posts = await m.PostSocial.all().prefetch_related("perfil")
    return {
        "coletadoEm": ser.iso(coleta.coletado_em) if coleta else "",
        "nota": coleta.nota if coleta else "",
        "redes": redes,
        "perfis": perfis,
        "posts": [{"id": x.id, "perfil": x.perfil_id, "rede": x.perfil.rede_id, "data": ser.iso(x.data),
                   "tipo": x.tipo, "curtidas": x.curtidas, "legenda": x.legenda, "url": x.url} for x in posts],
        "buscasYoutube": [{"termo": x.termo, "analisados": x.analisados, "doSetor": x.do_setor,
                           "resumo": x.resumo, "destaques": x.destaques} for x in await m.BuscaYoutube.all()],
    }
