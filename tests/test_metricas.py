"""
El backend de métricas de envíos y conversión.

Lo que Explee no da: cruzar envíos con conversiones y decir a qué segmento,
día y hora le fue mejor. Cada test fija los timestamps a mano para que la
agregación sea determinista.
"""
from __future__ import annotations

import pytest

from cliente_ia import metricas


@pytest.fixture(autouse=True)
def datos_limpios(tmp_path, monkeypatch):
    monkeypatch.setenv("MVCLIENTE_DIR_DATOS", str(tmp_path))
    metricas.borrar_todo()
    yield
    metricas.borrar_todo()


def _envio(programa="mvkobranzaia.com", canal="email", segmento="fintech",
           nivel="local", pais="UY", idioma="es", ts="2026-03-02T10:00:00+00:00", n=1):
    # 2026-03-02 es un lunes 10:00.
    return {"programa": programa, "canal": canal, "segmento": segmento,
            "nivel": nivel, "pais": pais, "idioma": idioma, "ts": ts, "n": n}


def test_registra_y_cuenta_envios():
    assert metricas.registrar_envios([_envio(), _envio(n=3)]) == 2
    r = metricas.resumen()
    assert r["envios"] == 4                     # 1 + 3
    assert r["conversiones"] == 0
    assert r["tasa_conversion"] == 0.0


def test_un_canal_desconocido_no_se_cuenta():
    assert metricas.registrar_envios([_envio(canal="telepatia")]) == 0
    assert metricas.resumen()["envios"] == 0


def test_la_tasa_de_conversion_cruza_los_dos_eventos():
    metricas.registrar_envios([_envio() for _ in range(10)])
    for _ in range(3):
        metricas.registrar_conversion({"programa": "mvkobranzaia.com",
                                       "segmento": "fintech", "canal": "email"})
    r = metricas.resumen()
    assert r["envios"] == 10
    assert r["conversiones"] == 3
    assert r["tasa_conversion"] == 0.3


def test_marca_el_mejor_dia_y_la_mejor_hora():
    """Lunes 10:00 convierte, viernes 18:00 no. Con muestra suficiente en
    cada bucket, el resumen tiene que coronar al lunes 10:00."""
    lunes_10 = "2026-03-02T10:00:00+00:00"
    viernes_18 = "2026-03-06T18:00:00+00:00"
    metricas.registrar_envios([_envio(ts=lunes_10) for _ in range(6)])
    metricas.registrar_envios([_envio(ts=viernes_18, segmento="retail") for _ in range(6)])
    for _ in range(5):
        metricas.registrar_conversion({"programa": "mvkobranzaia.com",
                                       "segmento": "fintech", "canal": "email",
                                       "ts": lunes_10})

    r = metricas.resumen()
    assert r["mejor_dia"]["clave"] == "lunes"
    assert r["mejor_hora"]["clave"] == "10:00"
    assert r["mejor_segmento"]["valor"] == "fintech"


def test_dia_y_hora_son_el_timing_del_click_no_del_envio():
    """El bug que destapó la prueba en vivo: el día en que se MANDA un correo
    y el día en que el destinatario hace CLICK no son el mismo. La tasa por
    segmento sigue siendo válida (envío y conversión comparten segmento), pero
    día/hora tienen que salir del click, no cruzar dos relojes distintos."""
    lunes_10 = "2026-03-02T10:00:00+00:00"       # se manda lunes 10
    martes_15 = "2026-03-03T15:00:00+00:00"      # entran martes 15

    metricas.registrar_envios([_envio(ts=lunes_10, segmento="fintech") for _ in range(20)])
    for _ in range(8):
        metricas.registrar_conversion({"programa": "mvkobranzaia.com",
                                       "segmento": "fintech", "canal": "email",
                                       "ts": martes_15})

    r = metricas.resumen()
    # La tasa por segmento es correcta: 8/20 de fintech.
    assert r["mejor_segmento"]["valor"] == "fintech"
    assert r["mejor_segmento"]["tasa"] == 0.4
    # El pico de conversión es cuando ENTRARON (martes 15), no cuando se mandó.
    assert r["mejor_dia"]["clave"] == "martes"
    assert r["mejor_hora"]["clave"] == "15:00"
    assert r["mejor_dia"]["conversiones"] == 8
    # Y día/hora NO fingen una tasa: son volumen de clicks.
    assert "tasa" not in r["mejor_dia"]


def test_no_corona_un_bucket_sin_muestra():
    """Una conversión sobre un envío es 100% y no dice nada: por debajo del
    mínimo, no se corona a nadie."""
    metricas.registrar_envios([_envio(segmento="nicho-raro")])
    metricas.registrar_conversion({"programa": "mvkobranzaia.com",
                                   "segmento": "nicho-raro", "canal": "email"})
    r = metricas.resumen()
    assert r["mejor_segmento"] is None
    assert r["muestra_suficiente"] is False


def test_cpm_y_cpa_solo_con_costo():
    metricas.registrar_envios([_envio() for _ in range(1000)])
    for _ in range(20):
        metricas.registrar_conversion({"programa": "mvkobranzaia.com", "canal": "email"})

    sin_costo = metricas.resumen()
    assert "cpm" not in sin_costo               # sin plata gastada no hay CPM

    con_costo = metricas.resumen(costo=100.0)
    assert con_costo["cpm"] == 100.0            # 100 / 1000 * 1000
    assert con_costo["cpa"] == 5.0              # 100 / 20


def test_filtra_por_programa():
    metricas.registrar_envios([_envio(programa="uno.com") for _ in range(4)])
    metricas.registrar_envios([_envio(programa="dos.com") for _ in range(6)])
    assert metricas.resumen(programa="uno.com")["envios"] == 4
    assert metricas.resumen(programa="dos.com")["envios"] == 6
    assert metricas.resumen()["envios"] == 10


def test_una_linea_corrupta_no_tumba_el_resumen(tmp_path):
    metricas.registrar_envios([_envio()])
    # Meter basura en el medio del archivo, como si una escritura se cortó.
    with open(tmp_path / metricas.ARCHIVO, "a", encoding="utf-8") as f:
        f.write("{esto no es json\n")
    metricas.registrar_envios([_envio()])
    assert metricas.resumen()["envios"] == 2    # ignora la línea rota


# ---------------------------------------------------------------------------
# El enlace de conversión firmado
# ---------------------------------------------------------------------------
def test_sin_secreto_el_traqueo_esta_apagado(monkeypatch):
    monkeypatch.delenv("MVCLIENTE_TRAQUEO_SECRETO", raising=False)
    assert metricas.hay_traqueo() is False
    assert metricas.verificar_traqueo("cualquier.cosa") is None


def test_el_token_de_conversion_viaja_y_vuelve(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "un-secreto-de-traqueo")
    token = metricas.firmar_traqueo("https://ejemplo.com/pt/",
                                    {"programa": "x.com", "canal": "email",
                                     "segmento": "fintech"})
    cuerpo = metricas.verificar_traqueo(token)
    assert cuerpo["u"] == "https://ejemplo.com/pt/"
    assert cuerpo["segmento"] == "fintech"


def test_un_token_manoseado_no_pasa(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "un-secreto-de-traqueo")
    token = metricas.firmar_traqueo("https://ejemplo.com/", {"canal": "email"})
    datos, _ = token.split(".", 1)
    assert metricas.verificar_traqueo(datos + ".firmafalsa") is None


def test_un_token_de_otro_secreto_no_pasa(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "el-secreto-de-alguien")
    token = metricas.firmar_traqueo("https://ejemplo.com/", {"canal": "email"})
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "otro-secreto-distinto")
    assert metricas.verificar_traqueo(token) is None


# ---------------------------------------------------------------------------
# Los endpoints, de punta a punta
# ---------------------------------------------------------------------------
def _cliente():
    from fastapi.testclient import TestClient

    from webapp.backend import api
    return TestClient(api.app)


def test_el_endpoint_registra_y_el_resumen_los_devuelve():
    cliente = _cliente()
    envios = {"eventos": [
        {"programa": "x.com", "canal": "email", "segmento": "fintech",
         "ts": "2026-03-02T10:00:00+00:00"} for _ in range(6)]}
    r = cliente.post("/api/metricas/envios", json=envios)
    assert r.status_code == 200 and r.json()["registrados"] == 6
    resumen = cliente.get("/api/metricas/resumen").json()
    assert resumen["envios"] == 6


def test_el_redirect_de_conversion_cuenta_el_click_y_rebota(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-del-redirect")
    cliente = _cliente()
    # Diez envíos para tener muestra, y una conversión vía el redirect.
    cliente.post("/api/metricas/envios", json={"eventos": [
        {"programa": "x.com", "canal": "email", "segmento": "fintech",
         "ts": "2026-03-02T10:00:00+00:00"} for _ in range(10)]})

    token = metricas.firmar_traqueo("https://ejemplo.com/pt/",
                                    {"programa": "x.com", "canal": "email",
                                     "segmento": "fintech"})
    r = cliente.get(f"/api/ir?t={token}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://ejemplo.com/pt/"

    resumen = cliente.get("/api/metricas/resumen?programa=x.com").json()
    assert resumen["conversiones"] == 1
    assert resumen["tasa_conversion"] == 0.1


def test_el_redirect_rechaza_firma_falsa(monkeypatch):
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-del-redirect")
    cliente = _cliente()
    r = cliente.get("/api/ir?t=cualquier.cosa", follow_redirects=False)
    assert r.status_code == 400
    assert metricas.resumen()["conversiones"] == 0     # no contó nada


def test_el_redirect_no_es_un_open_redirect(monkeypatch):
    """Aunque alguien lograra firmar un token (no puede sin el secreto), un
    esquema que no sea http/https se rechaza igual: el redirect nunca se
    convierte en un `javascript:` ni un `file:`."""
    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-del-redirect")
    cliente = _cliente()
    for veneno in ("javascript:alert(1)", "file:///etc/passwd",
                   "//evil.tld/phishing"):
        token = metricas.firmar_traqueo(veneno, {"canal": "email"})
        r = cliente.get(f"/api/ir?t={token}", follow_redirects=False)
        assert r.status_code == 400, veneno


def test_con_traqueo_el_correo_de_una_corrida_lleva_el_enlace_de_conversion(monkeypatch):
    """El cierre del lazo: con el traqueo encendido, una corrida real produce
    correos cuya landing pasa por `/api/ir`, y ese enlace, verificado, trae el
    segmento del prospecto — que es lo que hace medible la conversión."""
    from urllib.parse import parse_qs, urlsplit

    from cliente_ia import pipeline

    monkeypatch.setenv("MVCLIENTE_TRAQUEO_SECRETO", "secreto-de-la-corrida")
    monkeypatch.setenv("MVCLIENTE_URL_TRAQUEO", "https://mv-cliente-ia.vercel.app")

    corrida = pipeline.ejecutar("mvkobranzaia.com", modo="demo",
                                limite_prospectos=20, limite_emails=5,
                                enlaces={"sitio": "mvkobranzaia.com"})
    con_landing = [e for e in corrida.emails if e.landing_url]
    assert con_landing, "la corrida no produjo correos con landing"

    correo = con_landing[0]
    assert "/api/ir?" in correo.landing_url, correo.landing_url
    token = parse_qs(urlsplit(correo.landing_url).query)["t"][0]
    cuerpo = metricas.verificar_traqueo(token)
    assert cuerpo and cuerpo["u"].startswith("https://mvkobranzaia.com")
    assert cuerpo["canal"] == "email"
    assert cuerpo["programa"] == "mvkobranzaia.com"
    assert cuerpo.get("segmento")           # el sector del prospecto viajó
