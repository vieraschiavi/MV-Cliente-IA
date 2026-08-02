"""
Pipeline end-to-end sobre el caso real del proyecto: MV Kobra AI.
Es la prueba que responde "¿funciona de punta a punta?".
"""
from __future__ import annotations

from cliente_ia import almacen, exportar, geo, pipeline
from cliente_ia.modelos import FASES


def test_las_seis_fases_terminan_bien(corrida_kobra):
    assert corrida_kobra.estado == "listo", corrida_kobra.error
    assert [p.clave for p in corrida_kobra.pasos] == list(FASES)
    assert all(p.estado == "listo" for p in corrida_kobra.pasos)


def test_investiga_la_categoria_correcta(corrida_kobra):
    e = corrida_kobra.empresa
    assert e.nombre == "MV Kobra AI"
    assert "cobranza" in e.categoria.lower()
    # El ICP de una plataforma de cobranzas tiene que incluir a quien presta.
    sectores = " ".join(e.sectores_objetivo).lower()
    assert "banco" in sectores and "financiera" in sectores


def test_devuelve_la_cantidad_pedida(corrida_kobra):
    assert len(corrida_kobra.prospectos) == 60


def test_uruguay_encabeza_la_lista(corrida_kobra):
    niveles = [p.nivel for p in corrida_kobra.prospectos]
    # Los locales van todos antes que los latam, y esos antes que los del mundo.
    assert niveles == sorted(niveles, key=lambda n: ["local", "latam", "mundo"].index(n))
    assert niveles[0] == "local"
    assert corrida_kobra.prospectos[0].pais == "UY"


def test_las_tres_olas_estan_representadas(corrida_kobra):
    por_nivel = corrida_kobra.resumen()["prospectos_por_nivel"]
    assert por_nivel["local"] > 0
    assert por_nivel["latam"] > 0
    assert por_nivel["mundo"] > 0
    # Uruguay se lleva la tajada más grande — es la regla de reparto.
    assert por_nivel["local"] > por_nivel["latam"] > por_nivel["mundo"]


def test_hay_correos_en_los_tres_idiomas(corrida_kobra):
    por_idioma = corrida_kobra.resumen()["emails_por_idioma"]
    assert set(por_idioma) == set(geo.IDIOMAS), f"faltan idiomas: {por_idioma}"
    assert por_idioma["es"] > por_idioma["en"], "el grueso de la tanda es Uruguay/LATAM"


def test_cada_correo_esta_en_el_idioma_del_pais_del_decisor(corrida_kobra):
    decisores = {d.id: d for d in corrida_kobra.decisores}
    for e in corrida_kobra.emails:
        d = decisores[e.decisor_id]
        assert e.idioma == geo.idioma_de(d.pais), f"{d.pais} → {e.idioma}"


def test_los_correos_no_mezclan_idiomas():
    """
    Regresión: la propuesta de valor y el dolor venían del idioma de la
    interfaz, así que los correos en portugués y en inglés llevaban un
    párrafo en español en el medio.
    """
    corrida = pipeline.ejecutar("mvkobranzaia.com", modo="demo",
                                limite_prospectos=60, nombre="MV Kobra AI")
    marcas = {
        "en": ("Do you have 15 minutes", "predicts which debtors"),
        "pt": ("Você tem 15 minutos", "prevê quais devedores"),
        "es": ("¿Tenés 15 minutos", "predice qué deudores"),
    }
    ajenas = {
        "en": ("¿Tenés", "prioriza la cartera", "Você tem"),
        "pt": ("¿Tenés", "prioriza la cartera por valor esperado de recupero", "Do you have"),
        "es": ("Do you have", "Você tem"),
    }
    vistos = set()
    for e in corrida.emails:
        vistos.add(e.idioma)
        for esperado in marcas[e.idioma]:
            assert esperado in e.cuerpo, f"[{e.idioma}] falta «{esperado}»"
        for intrusa in ajenas[e.idioma]:
            assert intrusa not in e.cuerpo, f"[{e.idioma}] se coló «{intrusa}»"
    assert vistos == set(marcas)


def test_el_nombre_del_producto_no_se_duplica(corrida_kobra):
    """Regresión: el cuerpo decía «MV Kobra AI MV Kobra AI predice…»."""
    for e in corrida_kobra.emails:
        assert "MV Kobra AI MV Kobra AI" not in e.cuerpo


def test_los_correos_son_cortos(corrida_kobra):
    # Un correo en frío de más de 160 palabras no se lee.
    assert max(e.palabras for e in corrida_kobra.emails) <= 160


def test_un_solo_correo_por_empresa_en_la_primera_vuelta(corrida_kobra):
    por_prospecto: dict[str, int] = {}
    for e in corrida_kobra.emails:
        por_prospecto[e.prospecto_id] = por_prospecto.get(e.prospecto_id, 0) + 1
    assert max(por_prospecto.values()) == 1, "no se le escribe a dos personas de la misma casa"


def test_todo_el_demo_viene_marcado_como_sintetico(corrida_kobra):
    assert all(p.sintetico for p in corrida_kobra.prospectos)
    assert all(d.sintetico for d in corrida_kobra.decisores)


def test_es_determinista():
    a = pipeline.ejecutar("mvkobranzaia.com", modo="demo", limite_prospectos=30)
    b = pipeline.ejecutar("mvkobranzaia.com", modo="demo", limite_prospectos=30)
    assert [p.nombre for p in a.prospectos] == [p.nombre for p in b.prospectos]
    assert [e.asunto for e in a.emails] == [e.asunto for e in b.emails]


def test_dominio_vacio_falla_claro():
    try:
        pipeline.ejecutar("   ", modo="demo")
    except ValueError as e:
        assert "dominio" in str(e).lower()
    else:
        raise AssertionError("tendría que haber fallado")


def test_funciona_con_un_producto_que_no_es_de_cobranzas():
    """El motor no puede estar cableado a un solo caso."""
    c = pipeline.ejecutar("unaherramienta.com.uy", modo="demo", limite_prospectos=20)
    assert c.estado == "listo"
    assert len(c.prospectos) == 20
    assert c.empresa.pais == "UY"          # el TLD .com.uy fija el mercado base


def test_la_cadena_no_confunde_vacio_con_fallo():
    """Regresión: un sitio inmobiliario en modo «leer mi sitio» tumbaba la
    fase 2 con NotImplementedError. Su categoría no tiene competidores
    precargados y la cadena trataba el [] legítimo como «nadie respondió»."""
    from cliente_ia.proveedores.base import Proveedor, ProveedorEncadenado

    class NoSabe(Proveedor):
        nombre = "nosabe"

    class RespondeVacio(Proveedor):
        nombre = "vacio"

        def competencia(self, empresa):
            return []

    cadena = ProveedorEncadenado(NoSabe(), RespondeVacio())
    assert cadena.competencia(None) == []

    # Un proveedor que FALLA (no que no sabe) queda registrado en `errores`:
    # es lo que el pipeline muestra como aviso en vez de esconder el fallo.
    class Falla(Proveedor):
        nombre = "falla"

        def competencia(self, empresa):
            raise RuntimeError("clave inválida")

    con_fallo = ProveedorEncadenado(Falla(), RespondeVacio())
    assert con_fallo.competencia(None) == []
    assert con_fallo.errores and "falla · competencia" in con_fallo.errores[0]

    # Y cuando de verdad nadie responde, el error claro tiene que seguir ahí.
    try:
        ProveedorEncadenado(NoSabe()).competencia(None)
    except NotImplementedError:
        pass
    else:
        raise AssertionError("sin proveedores que respondan tiene que fallar")


def test_la_clave_de_la_interfaz_habilita_el_modo_ia(monkeypatch):
    """La clave pegada en Configuración vale igual que la del servidor: sin
    ninguna de las dos, `llm` cae honesto a `web`."""
    from cliente_ia import proveedores
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert proveedores.modo_efectivo("llm") == "web"
    assert proveedores.modo_efectivo("llm", "sk-ant-loquesea") == "llm"
    # Y la cadena se arma con el proveedor LLM adentro.
    cadena = proveedores.construir("llm", clave_ia="sk-ant-loquesea")
    assert "llm" in cadena.nombre


def test_proveedor_ia_elige_la_api_y_firma_los_avisos(monkeypatch):
    """La clave puede ser de Claude, ChatGPT, Gemini o Copilot. El nombre del
    proveedor tiene que viajar en la cadena (y por lo tanto en los avisos):
    «openai · competencia: …» le dice al usuario QUÉ clave falló."""
    from cliente_ia import proveedores
    from cliente_ia.proveedores.llm import ErrorLLM, ProveedorLLM
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    cadena = proveedores.construir("llm", clave_ia="sk-cualquiera",
                                   proveedor_ia="openai")
    assert "openai" in cadena.nombre

    # Un proveedor desconocido no se acepta en silencio.
    try:
        ProveedorLLM(clave="x", proveedor="grok")
    except ErrorLLM as e:
        assert "grok" in str(e)
    else:
        raise AssertionError("proveedor desconocido tenía que fallar")

    # Copilot es Azure OpenAI: sin la URL del endpoint no hay a quién llamar.
    try:
        ProveedorLLM(clave="x", proveedor="copilot")
    except ErrorLLM as e:
        assert "endpoint" in str(e)
    else:
        raise AssertionError("copilot sin endpoint tenía que fallar")
    p = ProveedorLLM(clave="x", proveedor="copilot",
                     endpoint="https://r.openai.azure.com/openai/deployments/g/chat/completions?api-version=1")
    assert p.nombre == "copilot"


def test_una_corrida_con_clave_openai_falsa_termina_con_aviso(monkeypatch):
    """Camino completo con proveedor no-Claude: la llamada REST falla (clave
    falsa, sin red), la cadena absorbe el error, la corrida termina con demo y
    el aviso nombra a openai — nunca la URL ni la clave. La fase web también
    se anula: el test no puede depender de que haya internet."""
    from cliente_ia.proveedores import llm as mod_llm
    from cliente_ia.proveedores import web as mod_web

    def _sin_red(self, url, cuerpo, cabeceras):
        raise mod_llm.ErrorLLM("openai respondió 401: clave inválida")

    def _sin_web(self, dominio):
        raise mod_web.ErrorWeb("sin red en el test")

    monkeypatch.setattr(mod_llm.ProveedorLLM, "_post_json", _sin_red)
    monkeypatch.setattr(mod_web.ProveedorWeb, "investigar", _sin_web)
    c = pipeline.ejecutar("mvkobranzaia.com", modo="llm", limite_prospectos=10,
                          clave_ia="sk-falsa", proveedor_ia="openai")
    assert c.estado == "listo"          # la demo cubre lo que la IA no pudo
    assert any("openai" in a for a in c.avisos)
    assert not any("sk-falsa" in a for a in c.avisos)


def test_empresa_real_no_lleva_persona_ni_correo_inventado():
    """Cuando la IA trae una empresa REAL, la fase 5 no le fabrica un nombre
    ni una casilla (un correo inventado sobre un dominio real puede caer en
    una persona real). Entrega el cargo y la búsqueda de LinkedIn armada."""
    from cliente_ia.modelos import Prospecto
    from cliente_ia.proveedores.demo import ProveedorDemo

    demo = ProveedorDemo("es")
    real = Prospecto(id="p0001", nombre="Empresa Real SA", dominio="empresareal.com.uy",
                     sector="Software B2B y servicios profesionales", pais="UY",
                     ciudad="Montevideo", empleados=50, descripcion="", senales=[],
                     dolor="x", campana_id="local-saas_b2b", nivel="local",
                     prioridad=1, idioma="es", sintetico=False, fuente="llm")
    decisores = demo.decisores([real], 3)
    assert decisores, "tiene que proponer cargos igual"
    for d in decisores:
        assert d.nombre == ""
        assert d.email == ""
        assert "linkedin.com/search" in d.linkedin
        assert not d.sintetico
        assert d.cargo


def test_decisores_sinteticos_no_repiten_nombre():
    """Dos empresas distintas sacaban el mismo «Federico Quintana» por choque
    de semillas y la lista entera parecía inventada a mano."""
    c = pipeline.ejecutar("mvkobranzaia.com", modo="demo", limite_prospectos=40)
    nombres = [d.nombre for d in c.decisores if d.nombre]
    assert len(nombres) == len(set(nombres)), "hay nombres repetidos"


def test_correo_de_empresa_real_saluda_con_hueco_no_vacio():
    from cliente_ia import redaccion
    from cliente_ia.modelos import Decisor, Prospecto
    from cliente_ia.proveedores.demo import ProveedorDemo

    empresa = ProveedorDemo("es").investigar("mvkobranzaia.com")
    p = Prospecto(id="p0001", nombre="Empresa Real SA", dominio="empresareal.com.uy",
                  sector="Software B2B", pais="UY", ciudad="Montevideo",
                  empleados=50, descripcion="", senales=["crece"], dolor="x",
                  campana_id="local-saas_b2b", nivel="local", prioridad=1,
                  idioma="es", sintetico=False, fuente="llm")
    d = Decisor(id="d00001", prospecto_id="p0001", nombre="", cargo="Head of Growth",
                empresa=p.nombre, pais="UY", email="", linkedin="https://x",
                seniority="director", idioma="es", sintetico=False, fuente="llm")
    correo = redaccion.redactar(d, p, empresa, None, firma="MV")
    assert "[nombre]" in correo.cuerpo
    assert "Hola :" not in correo.cuerpo
    assert correo.para == ""


def test_contactos_publicos_salen_del_sitio_de_la_empresa(monkeypatch):
    """El rastreador lee el sitio REAL del prospecto y saca sólo lo publicado:
    correo comercial del propio dominio primero, teléfono, LinkedIn de
    empresa e Instagram de perfil (no posts). Basura tipo foo@2x.png, no."""
    from cliente_ia.proveedores import contactos

    PORTADA = """
    <html><body>
      <a href="/contacto">Contacto</a>
      <img src="logo@2x.png">
      <a href="https://www.instagram.com/p/abc123/">post</a>
      <a href="https://www.instagram.com/empresareal.uy">IG</a>
      <a href="https://www.linkedin.com/company/empresa-real">in</a>
    </body></html>
    """
    CONTACTO = """
    <html><body>
      <a href="mailto:info@empresareal.com.uy">Escribinos</a>
      <p>gerente.personal@gmail.com</p>
      <a href="tel:+598 99 123 456">Llamanos</a>
    </body></html>
    """

    def bajar_falso(url, timeout=5):
        return CONTACTO if "contacto" in url else PORTADA

    monkeypatch.setattr(contactos, "bajar", bajar_falso)
    c = contactos.contactos_de("empresareal.com.uy")
    assert c["email"] == "info@empresareal.com.uy"      # el del dominio, primero
    assert "gerente.personal@gmail.com" in c["emails"]  # publicado, se lista
    assert all(not e.endswith(".png") for e in c["emails"])
    assert c["telefono"] == "+598 99 123 456"
    assert c["linkedin"] == "https://www.linkedin.com/company/empresa-real"
    assert c["instagram"] == "https://www.instagram.com/empresareal.uy"


def test_el_correo_va_a_la_casilla_publica_de_la_empresa_real():
    """Sin persona identificada, el destinatario es la casilla comercial que
    la empresa publica — no una inventada. Sin casilla publicada, vacío."""
    from cliente_ia import redaccion
    from cliente_ia.modelos import Decisor, Prospecto
    from cliente_ia.proveedores.demo import ProveedorDemo

    empresa = ProveedorDemo("es").investigar("mvkobranzaia.com")
    p = Prospecto(id="p0001", nombre="Empresa Real SA", dominio="empresareal.com.uy",
                  sector="Software B2B", pais="UY", ciudad="Montevideo",
                  empleados=50, descripcion="", senales=["crece"], dolor="x",
                  campana_id="local-saas_b2b", nivel="local", prioridad=1,
                  idioma="es", sintetico=False, fuente="llm",
                  contactos={"email": "info@empresareal.com.uy"})
    d = Decisor(id="d00001", prospecto_id="p0001", nombre="", cargo="CEO",
                empresa=p.nombre, pais="UY", email="", linkedin="https://x",
                seniority="c-level", idioma="es", sintetico=False, fuente="llm")
    correo = redaccion.redactar(d, p, empresa, None, firma="MV")
    assert correo.para == "info@empresareal.com.uy"
    p.contactos = {}
    assert redaccion.redactar(d, p, empresa, None, firma="MV").para == ""


def test_proyeccion_financiera_es_matematica_declarada():
    """La proyección sale SOLO de los números del usuario: escenarios con
    multiplicadores fijos y a la vista, meses 3-24, y con ads entran
    gasto_ads/CAC clientes más por mes."""
    from cliente_ia import analisis

    r = analisis.proyectar(precio=100, nuevos_por_mes=2, churn_pct=5,
                           gasto_fijo=500, costo_por_cliente=10,
                           gasto_ads=300, cac=150)
    assert r["supuestos"] == analisis.SUPUESTOS
    for escenario in ("pesimista", "base", "optimista"):
        for modo in ("sin_ads", "con_ads"):
            filas = r["escenarios"][escenario][modo]["filas"]
            assert [f["mes"] for f in filas] == [3, 6, 9, 12, 18, 24]
    # Con ads siempre hay al menos los mismos clientes que sin ads.
    base = r["escenarios"]["base"]
    for sin_f, con_f in zip(base["sin_ads"]["filas"], base["con_ads"]["filas"],
                            strict=True):
        assert con_f["clientes"] >= sin_f["clientes"]
    # El optimista termina con más clientes que el pesimista.
    assert (r["escenarios"]["optimista"]["sin_ads"]["filas"][-1]["clientes"]
            > r["escenarios"]["pesimista"]["sin_ads"]["filas"][-1]["clientes"])
    # Aritmética de una fila: el gasto se desglosa y el neto cierra.
    f = base["con_ads"]["filas"][0]
    assert f["neto_mes"] == f["ingresos"] - f["gastos"]
    assert f["gastos"] == f["gasto_fijo"] + f["gasto_variable"] + f["gasto_ads"]
    assert f["gasto_ads"] == 300
    assert base["sin_ads"]["filas"][0]["gasto_ads"] == 0


def test_el_error_http_del_proveedor_no_repite_la_clave(monkeypatch):
    """OpenAI repite la clave entera en su mensaje de 401. Ese texto termina
    en los avisos de la corrida (que se guardan) y en el log del servidor,
    así que se tacha antes de armar el error."""
    import io
    import urllib.error

    from cliente_ia.proveedores.llm import ErrorLLM, ProveedorLLM

    def _falla_401(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://api.openai.com/v1/chat/completions", 401, "Unauthorized",
            {}, io.BytesIO(b'{"error": {"message": "Incorrect API key '
                           b'provided: sk-super-secreta-123"}}'))

    monkeypatch.setattr("urllib.request.urlopen", _falla_401)
    p = ProveedorLLM(clave="sk-super-secreta-123", proveedor="openai")
    try:
        p._pedir("hola")
    except ErrorLLM as e:
        assert "sk-super-secreta-123" not in str(e)
        assert "401" in str(e)
    else:
        raise AssertionError("el 401 tenía que propagarse como ErrorLLM")


def test_mercado_solo_uruguay_llena_el_cupo_con_locales():
    """El filtro «sólo Uruguay» renormaliza el reparto: la ola local se lleva
    el límite entero, no el 45% que le tocaba cuando estaban las tres olas."""
    c = pipeline.ejecutar("mvkobranzaia.com", modo="demo",
                          limite_prospectos=20, mercado="local")
    assert c.estado == "listo"
    assert c.mercado == "local"
    assert len(c.prospectos) == 20
    assert all(p.nivel == "local" for p in c.prospectos)
    assert all(p.pais == "UY" for p in c.prospectos)


def test_mercado_solo_latam():
    c = pipeline.ejecutar("mvkobranzaia.com", modo="demo",
                          limite_prospectos=20, mercado="latam")
    assert c.estado == "listo"
    assert all(p.nivel == "latam" for p in c.prospectos)


def test_mercado_invalido_falla_claro():
    try:
        pipeline.ejecutar("mvkobranzaia.com", modo="demo", mercado="marte")
    except ValueError as e:
        assert "ercado" in str(e)
    else:
        raise AssertionError("tendría que haber fallado")


def test_guardar_y_recuperar_no_pierde_nada(corrida_kobra):
    almacen.guardar(corrida_kobra)
    vuelta = almacen.cargar(corrida_kobra.id)
    assert vuelta is not None
    assert vuelta.a_dict() == corrida_kobra.a_dict()
    assert [c["id"] for c in almacen.listar()] == [corrida_kobra.id]


def test_export_csv_tiene_una_fila_por_decisor(corrida_kobra):
    # Se parsea con el módulo csv y no cortando por "\n": el cuerpo del correo
    # lleva saltos de línea adentro de comillas y contarlos a mano da cualquier
    # cosa (741 "líneas" para 180 filas).
    import csv as csvmod
    import io

    texto = exportar.a_csv(corrida_kobra)
    filas = list(csvmod.DictReader(io.StringIO(texto)))
    assert len(filas) == len(corrida_kobra.decisores)
    assert texto.startswith("prioridad,nivel,pais,score")
    # Los prospectos uruguayos tienen que salir primero también en el archivo.
    assert filas[0]["nivel"] == "local"
    assert filas[0]["pais"] == "UY"
    # Y el archivo tiene que decir que los datos son sintéticos.
    assert all(f["sintetico"] == "sí" for f in filas)


def test_export_xlsx_se_genera(corrida_kobra):
    destino = exportar.guardar_xlsx(corrida_kobra)
    assert destino.exists() and destino.stat().st_size > 5000


def test_la_semilla_del_catalogo_esta_versionada():
    """
    Regresión: `.gitignore` tenía `datos/` sin barra inicial, así que git lo
    aplicaba en cualquier nivel y se comía `cliente_ia/datos/mercado.json`.
    En la máquina de desarrollo no se nota —el archivo está ahí, sin
    versionar— pero el clon limpio queda sin él y no arranca ni un test.
    Un archivo que el paquete necesita para funcionar tiene que estar en el
    repo, y eso no lo verifica ninguna importación.
    """
    import subprocess
    from pathlib import Path

    import pytest

    raiz = Path(__file__).resolve().parent.parent
    necesarios = ["cliente_ia/datos/mercado.json"]
    try:
        r = subprocess.run(["git", "ls-files", *necesarios],
                           cwd=raiz, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git no disponible")
    if r.returncode != 0:
        pytest.skip("no es un repositorio git")
    versionados = set(r.stdout.split())
    faltan = [n for n in necesarios if n not in versionados]
    assert not faltan, f"archivos del paquete sin versionar: {faltan}"
