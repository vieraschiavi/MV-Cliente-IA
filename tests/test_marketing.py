"""Pestaña Marketing digital: auditoría medida, puntajes declarados, sin inventar."""
from __future__ import annotations

import pytest

from cliente_ia import marketing

SITIO_COMPLETO = """<!doctype html><html lang="es"><head>
<title>Cobranzas con IA para financieras | Acme</title>
<meta name="description" content="Automatizá la cobranza de tu cartera con agentes de IA que llaman, escriben y negocian por vos, en español y portugués.">
<meta name="viewport" content="width=device-width">
<link rel="canonical" href="https://acme.com/"><link rel="icon" href="/f.png">
<meta property="og:title" content="Acme"><meta property="og:image" content="https://acme.com/og.png">
<meta name="twitter:card" content="summary">
<link rel="alternate" hreflang="pt" href="https://acme.com/pt/">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"Acme"}</script>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-ABC123XYZ"></script>
<script>fbq('init', '123');</script>
</head><body><h1>Cobranzas con IA</h1>
<img src="a.png" alt="panel"><img src="b.png" alt="agente">
<form><input type="email" name="email"><button>Agendá una demo</button></form>
<a href="https://wa.me/59899000000">WhatsApp</a><a href="mailto:hola@acme.com">Escribinos</a>
<a href="https://www.linkedin.com/company/acme">LinkedIn</a>
<p>""" + "palabra " * 400 + "</p></body></html>"

SITIO_POBRE = "<html><head><title>Inicio</title></head><body><h1>A</h1><h1>B</h1><img src=x></body></html>"


def _bajar(paginas: dict[str, str], pedidos: list | None = None):
    def bajar(url, timeout=0):
        if pedidos is not None:
            pedidos.append(url)
        for clave, html in paginas.items():
            if url.rstrip("/").endswith(clave):
                return html
        raise OSError("404")
    return bajar


@pytest.fixture(autouse=True)
def sin_redes(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_METRICAS_REDES", "0")


def test_un_sitio_bien_armado_puntua_alto_y_casi_no_tiene_recomendaciones():
    a = marketing.auditar("acme.com", bajar=_bajar({
        "acme.com": SITIO_COMPLETO, "robots.txt": "User-agent: *",
        "sitemap.xml": "<urlset><url><loc>https://acme.com/</loc></url></urlset>"}))
    assert a["puntajes"]["sub"]["seo"] == 100
    assert a["medicion"]["ga4"] and a["medicion"]["meta_pixel"]
    assert a["conversion"]["formulario"] and a["conversion"]["whatsapp"] and a["conversion"]["cta"] >= 1
    assert a["tecnica"]["robots"] and a["tecnica"]["sitemap"]
    assert a["redes"].get("linkedin")
    codigos = {r["codigo"] for r in a["recomendaciones"]}
    assert not codigos & {"sin_analitica", "sin_formulario", "sin_cta", "titulo", "descripcion", "h1"}


def test_un_sitio_pobre_recibe_las_recomendaciones_de_lo_que_le_falta():
    a = marketing.auditar("pobre.com", bajar=_bajar({"pobre.com": SITIO_POBRE}))
    codigos = [r["codigo"] for r in a["recomendaciones"]]
    for esperado in ("sin_analitica", "sin_formulario", "sin_cta", "titulo", "descripcion", "h1",
                     "alt", "sitemap", "contenido", "sin_redes"):
        assert esperado in codigos
    h1 = next(r for r in a["recomendaciones"] if r["codigo"] == "h1")
    assert h1["datos"] == {"n": 2}
    # Las altas primero: es el orden en que conviene arreglar.
    prioridades = [r["prioridad"] for r in a["recomendaciones"]]
    assert prioridades == sorted(prioridades, key=["alta", "media", "baja"].index)
    assert a["puntajes"]["total"] < 40


def test_el_total_es_el_promedio_ponderado_con_los_pesos_declarados():
    a = marketing.auditar("acme.com", bajar=_bajar({"acme.com": SITIO_COMPLETO}))
    sub = a["puntajes"]["sub"]
    esperado = round(sum(sub[k] * p for k, p in marketing.PESOS.items()) / sum(marketing.PESOS.values()))
    assert a["puntajes"]["total"] == esperado
    assert a["pesos"] == marketing.PESOS


def test_un_sitio_que_no_responde_no_inventa_puntajes():
    a = marketing.auditar("caido.com", bajar=_bajar({}))
    assert a["error"] == "no_se_pudo_leer" and "puntajes" not in a


def test_prueba_con_www_si_el_dominio_pelado_no_responde():
    pedidos: list[str] = []
    a = marketing.auditar("solowww.com", bajar=_bajar({"www.solowww.com": SITIO_POBRE}, pedidos))
    assert "error" not in a and pedidos[:2] == ["solowww.com", "www.solowww.com"]


def test_la_competencia_se_audita_igual_y_queda_en_el_benchmark():
    a = marketing.auditar("acme.com", [
        {"dominio": "pobre.com", "nombre": "Pobre"}, {"dominio": "caido.com", "nombre": "Caído"}],
        bajar=_bajar({"acme.com": SITIO_COMPLETO, "pobre.com": SITIO_POBRE}))
    bench = {b["dominio"]: b for b in a["benchmark"]}
    assert bench["pobre.com"]["puntaje"] < a["puntajes"]["total"]
    assert bench["caido.com"]["error"] == "no_se_pudo_leer"


def test_cuota_de_voz_solo_suma_cifras_medidas():
    propias = {"linkedin": {"estado": "ok", "seguidores": 1000},
               "instagram": {"estado": "no_disponible"}}
    comps = [{"metricas": {"linkedin": {"estado": "ok", "seguidores": 3000},
                           "instagram": {"estado": "ok", "seguidores": 500}}},
             {"metricas": {"linkedin": {"estado": "no_disponible"}}}]
    c = marketing.cuota_de_voz(propias, comps)
    assert c["linkedin"] == {"propios": 1000, "competencia": 3000, "competidores_medidos": 1,
                             "cuota": 0.25}
    # Sin cifra propia no hay cuota: un «no disponible» no es un cero.
    assert c["instagram"]["propios"] is None and c["instagram"]["cuota"] is None


def test_la_api_audita_y_pone_tope_por_ip(monkeypatch):
    from fastapi.testclient import TestClient

    from webapp.backend import api
    monkeypatch.setattr(marketing, "auditar", lambda d, c: {"dominio": d, "ok": True})
    monkeypatch.setattr(api, "_MARKETING_POR_IP", {})
    cliente = TestClient(api.app)
    for _ in range(api.MARKETING_TOPE):
        assert cliente.post("/api/marketing", json={"dominio": "acme.com"}).status_code == 200
    assert cliente.post("/api/marketing", json={"dominio": "acme.com"}).status_code == 429
