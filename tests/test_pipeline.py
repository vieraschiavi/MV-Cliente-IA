"""
Pipeline end-to-end sobre el caso real del proyecto: MV Kobra AI.
Es la prueba que responde "¿funciona de punta a punta?".
"""
from __future__ import annotations

import time
import urllib.parse

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


def test_el_pais_del_cliente_encabeza_la_lista(corrida_kobra):
    niveles = [p.nivel for p in corrida_kobra.prospectos]
    # Los locales van todos antes que los regionales, y esos antes que el mundo.
    assert niveles == sorted(niveles, key=geo.NIVELES.index)
    assert niveles[0] == geo.NIVEL_LOCAL
    # El dominio no tiene TLD nacional y la interfaz está en español, así que
    # el país base cae en Uruguay. Lo que se verifica no es "Uruguay": es que
    # el país base, sea cual sea, encabece.
    assert corrida_kobra.prospectos[0].pais == corrida_kobra.pais_base


def test_otro_pais_base_manda_su_propia_ola_local():
    """La regla es relativa: con Alemania elegida, la ola local es alemana y
    la regional es europea — nada de Uruguay ni de LATAM."""
    c = pipeline.ejecutar("mvkobranzaia.com", modo="demo",
                          limite_prospectos=40, pais_base="DE")
    assert c.estado == "listo", c.error
    assert c.pais_base == "DE"
    locales = [p for p in c.prospectos if p.nivel == geo.NIVEL_LOCAL]
    assert locales and all(p.pais == "DE" for p in locales)
    regionales = [p for p in c.prospectos if p.nivel == geo.NIVEL_REGIONAL]
    assert regionales
    assert all(geo.region_de(p.pais) == "EUROPA" for p in regionales)
    assert all(p.pais != "DE" for p in regionales)
    # Y Uruguay, que antes era intocable, ahora es un mercado del montón.
    assert geo.nivel_de("UY", "DE") == geo.NIVEL_MUNDO


def test_las_tres_olas_estan_representadas(corrida_kobra):
    por_nivel = corrida_kobra.resumen()["prospectos_por_nivel"]
    assert all(por_nivel[n] > 0 for n in geo.NIVELES)
    # El país del cliente se lleva la tajada más grande — es la regla de reparto.
    assert (por_nivel[geo.NIVEL_LOCAL] > por_nivel[geo.NIVEL_REGIONAL]
            > por_nivel[geo.NIVEL_MUNDO])


def test_hay_correos_en_los_tres_idiomas(corrida_kobra):
    por_idioma = corrida_kobra.resumen()["emails_por_idioma"]
    assert set(por_idioma) == set(geo.IDIOMAS), f"faltan idiomas: {por_idioma}"
    assert por_idioma["es"] > por_idioma["en"], \
        "con el país base en Uruguay el grueso de la tanda habla español"


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
        "en": ("Want me to show you on", "predicts which debtors"),
        "pt": ("Quer que eu mostre sobre o caso", "prevê quais devedores"),
        "es": ("¿Querés que te lo muestre", "predice qué deudores"),
    }
    ajenas = {
        "en": ("¿Querés", "prioriza la cartera", "Quer que eu mostre"),
        "pt": ("¿Querés", "prioriza la cartera por valor esperado de recupero",
               "Want me to show"),
        "es": ("Want me to show", "Quer que eu mostre"),
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
    """La clave puede ser de Claude, ChatGPT, Gemini, Copilot o Grok. El
    nombre del proveedor tiene que viajar en la cadena (y por lo tanto en los
    avisos): «openai · competencia: …» le dice al usuario QUÉ clave falló."""
    from cliente_ia import proveedores
    from cliente_ia.proveedores.llm import ErrorLLM, ProveedorLLM
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    cadena = proveedores.construir("llm", clave_ia="sk-cualquiera",
                                   proveedor_ia="openai")
    assert "openai" in cadena.nombre

    # Un proveedor desconocido no se acepta en silencio.
    try:
        ProveedorLLM(clave="x", proveedor="bing")
    except ErrorLLM as e:
        assert "bing" in str(e)
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


def test_una_corrida_con_clave_openai_falsa_FALLA_y_lo_dice(monkeypatch):
    """Camino completo con proveedor no-Claude y clave falsa. Antes la cadena
    absorbía el error y la corrida "terminaba bien" rellena de datos demo —
    un usuario real pidió IA de su país y recibió sintético de cualquier
    lado, con el aviso perdido abajo de todo. Ahora el modo IA es estricto:
    la corrida FALLA, el error nombra a openai, y ni la URL ni la clave
    aparecen por ningún lado."""
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
    assert c.estado == "error"          # pidió IA: sin IA no hay corrida
    assert "openai" in (c.error or "")
    assert "sk-falsa" not in (c.error or "")
    assert not any("sk-falsa" in a for a in c.avisos)
    # Y no quedó ningún dato sintético haciéndose pasar por resultado de IA.
    assert not c.competidores and not c.prospectos


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
        # Sin página de LinkedIn conocida: búsqueda de personas afinada con
        # cargo + empresa + PAÍS (gente que trabaja ahí, no homónimos).
        assert "linkedin.com/search" in d.linkedin
        assert "Uruguay" in urllib.parse.unquote(d.linkedin)
        assert not d.sintetico
        assert d.cargo

    # Con la página de LinkedIn de la empresa rastreada, el enlace va
    # directo a sus empleados ACTUALES filtrados por el cargo.
    real.contactos = {"linkedin": "https://uy.linkedin.com/company/empresa-real"}
    con_pagina = demo.decisores([real], 2)
    for d in con_pagina:
        assert d.linkedin.startswith(
            "https://uy.linkedin.com/company/empresa-real/people/?keywords=")


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
      <script>const v = "bootstrap@4.0.0";</script>
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
    assert all("bootstrap" not in e for e in c["emails"])
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


def test_el_filtro_de_mercado_se_hace_cumplir_en_la_competencia():
    """Con «sólo Uruguay» los competidores con base local van primero, los
    de afuera sólo quedan si venden ahí, y si no hay ni uno local la corrida
    lo dice — antes el filtro era una frase del prompt y la lista salía
    global sin contexto."""
    from cliente_ia.modelos import Competidor
    from cliente_ia.proveedores.llm import ProveedorLLM

    def _comp(dominio, pais, sol):
        return Competidor(dominio=dominio, nombre=dominio, posicionamiento="x",
                          pais=pais, solapamiento=sol, fuente="llm")

    p = ProveedorLLM(clave="sk-x", proveedor="openai", mercado="local")
    lista = [_comp("global.com", "US", 0.9), _comp("local.uy", "UY", 0.6),
             _comp("brasil.br", "BR", 0.8)]
    vende = {"global.com": True, "local.uy": True, "brasil.br": False}
    r = p._recortar_competencia(lista, vende, "UY")
    assert [c.dominio for c in r] == ["local.uy", "global.com"]  # UY primero; BR afuera
    assert not p.notas                                  # hay local: sin nota

    # Sin ninguno de base local, la lista queda pero la nota lo explica.
    p2 = ProveedorLLM(clave="sk-x", proveedor="openai", mercado="local")
    r2 = p2._recortar_competencia([_comp("global.com", "US", 0.9)],
                                  {"global.com": True}, "UY")
    assert r2 and p2.notas and "Uruguay" in p2.notas[0] or "UY" in p2.notas[0]


def test_sin_locales_hay_segunda_pasada_dedicada(monkeypatch):
    """Reportado con captura: «sólo Uruguay» devolvía diez competidores
    AR/CO/BR/US y ninguno UY. Si la primera pasada no trae NINGUNO con base
    en el recorte, se pregunta de nuevo con foco exclusivo en ese país; los
    locales encontrados van primero. Y si tampoco aparecen, queda la nota."""
    import json as jsonmod

    from cliente_ia.proveedores.demo import ProveedorDemo
    from cliente_ia.proveedores.llm import ProveedorLLM

    empresa = ProveedorDemo("es").investigar("inmobiliariamv.com.uy")
    extranjeros = jsonmod.dumps([
        {"dominio": "tokkobroker.com", "nombre": "Tokko", "posicionamiento": "x",
         "pais": "AR", "vende_en_objetivo": True, "solapamiento": 0.6},
        {"dominio": "wasi.co", "nombre": "Wasi", "posicionamiento": "x",
         "pais": "CO", "vende_en_objetivo": True, "solapamiento": 0.45},
    ])
    local = jsonmod.dumps([
        {"dominio": "tasador.uy", "nombre": "Tasador UY", "posicionamiento": "x",
         "pais": "UY", "solapamiento": 0.7},
    ])

    llamadas = []

    def pedir_falso(self, prompt, max_tokens=8000):
        llamadas.append(prompt)
        return local if "Segunda pasada" in prompt else extranjeros

    monkeypatch.setattr(ProveedorLLM, "_pedir", pedir_falso)
    p = ProveedorLLM(clave="sk-x", proveedor="openai", mercado="local")
    r = p.competencia(empresa)
    assert len(llamadas) == 2, "sin locales en la primera, tiene que insistir"
    assert r[0].dominio == "tasador.uy" and r[0].pais == "UY"
    assert [c.dominio for c in r[1:]] == ["tokkobroker.com", "wasi.co"]
    assert not p.notas                                  # apareció un local: sin nota

    # Si la segunda pasada tampoco encuentra, los regionales quedan con nota.
    monkeypatch.setattr(ProveedorLLM, "_pedir",
                        lambda self, pr, t=8000: "[]" if "Segunda pasada" in pr
                        else extranjeros)
    p2 = ProveedorLLM(clave="sk-x", proveedor="openai", mercado="local")
    r2 = p2.competencia(empresa)
    assert [c.pais for c in r2] == ["AR", "CO"]
    assert p2.notas and "base" in p2.notas[0]

    # Con un local en la PRIMERA pasada no se gasta una llamada extra.
    con_local = jsonmod.dumps([
        {"dominio": "local.uy", "nombre": "L", "posicionamiento": "x",
         "pais": "UY", "vende_en_objetivo": True, "solapamiento": 0.5},
    ])
    cuenta = []
    monkeypatch.setattr(ProveedorLLM, "_pedir",
                        lambda self, pr, t=8000: cuenta.append(1) or con_local)
    p3 = ProveedorLLM(clave="sk-x", proveedor="openai", mercado="local")
    p3.competencia(empresa)
    assert len(cuenta) == 1


def test_un_sector_de_la_ia_no_revienta_al_demo_de_respaldo():
    """KeyError 'electricistasysanitarios' en producción: la campaña con IA
    trae sectores reales que no están en el catálogo demo, y cuando la fase 4
    caía al demo, éste indexaba el catálogo con esa clave y tumbaba la
    corrida. Ahora usa el sector genérico como base y muestra el nombre y el
    dolor de la campaña."""
    from cliente_ia.modelos import Campana
    from cliente_ia.proveedores.demo import ProveedorDemo

    demo = ProveedorDemo("es")
    empresa = demo.investigar("mvagendate.com")
    campana = Campana(id="local-electricistasysanitarios",
                      nombre="Electricistas y sanitarios · LOCAL",
                      sector="Electricistas y sanitarios", nivel="local",
                      prioridad=1, paises=["UY"],
                      angulo="x", dolor="pierden trabajos por no atender",
                      prueba="", idioma="es")
    prospectos = demo.prospectos(empresa, [campana], 6)
    assert prospectos, "el respaldo tiene que producir prospectos igual"
    assert all(p.sector == "Electricistas y sanitarios" for p in prospectos)
    assert all(p.dolor == "pierden trabajos por no atender" for p in prospectos)


def test_json_truncado_se_rescata_hasta_el_ultimo_objeto_completo():
    """«Expecting value: line 32 column 71» tiraba la ola entera: si el
    modelo se corta a mitad del objeto 31, los 30 completos sirven."""
    from cliente_ia.proveedores.llm import ErrorLLM, _json_del_texto

    truncado = '[{"nombre": "A", "dominio": "a.com"}, {"nombre": "B", "dominio": "b.com"}, {"nombre": "C", "domi'
    r = _json_del_texto(truncado)
    assert [x["nombre"] for x in r] == ["A", "B"]
    # Basura sin ningún objeto completo sigue fallando con el error claro.
    try:
        _json_del_texto('[{"nombre": sin comillas')
    except ErrorLLM:
        pass
    else:
        raise AssertionError("basura irrecuperable tenía que fallar")


def test_una_palabra_suelta_del_html_no_clasifica_el_producto():
    """El bug: «recovery» matcheaba DENTRO de «accountRecovery» (una ruta del
    panel de Vercel) y clasificaba el producto como cobranzas. Las pistas se
    buscan como principio de palabra, no como subcadena."""
    from cliente_ia.proveedores.demo import CATEGORIA_DEFAULT, ProveedorDemo

    demo = ProveedorDemo("es")
    ruido = "wellknown accountRecovery api apps atom breadcrumbs claim deployment"
    assert demo.detectar_categoria(ruido) == CATEGORIA_DEFAULT
    # Y lo que sí es del rubro se sigue detectando, con y sin acentos.
    assert demo.detectar_categoria("plataforma de cobranzas") == "cobranzas"
    assert demo.detectar_categoria("gestão de cobrança") == "cobranzas"
    assert demo.detectar_categoria("debt recovery software") == "cobranzas"


def test_un_panel_sin_descripcion_no_se_perfila_y_lo_dice(monkeypatch):
    """Una página sin título, descripción ni h1 (un panel, o una app que se
    dibuja por JavaScript) no describe ningún producto: no se perfila con IA
    —sería inventar— y la corrida explica qué pasó y qué hacer."""
    from cliente_ia.proveedores import web as mod_web

    PANEL = "<html><body><div>Skip to content Projects Deployments Logs</div></body></html>"
    monkeypatch.setattr(mod_web, "bajar", lambda url, timeout=12: PANEL)

    empresa = mod_web.ProveedorWeb("es").investigar("vercel.com/mv13/mv-agendate-ia")
    assert empresa.resumen_sitio == "", "sin producto que leer, no se finge texto real"

    perfilado = []
    from cliente_ia.proveedores.base import ProveedorEncadenado
    monkeypatch.setattr(ProveedorEncadenado, "perfilar",
                        lambda self, e: perfilado.append(e) or e)

    c = pipeline.ejecutar("vercel.com/mv13/mv-agendate-ia", modo="web",
                          limite_prospectos=5)
    assert not perfilado, "no se perfila sobre una página sin producto"
    assert any("no hay una descripción de tu producto" in a for a in c.avisos)
    assert any("URL pública" in a for a in c.avisos)


def test_el_nicho_sale_del_sitio_real_no_del_catalogo(monkeypatch):
    """El bug: a un producto de text-to-SQL le aparecían los sectores del
    catálogo demo (cobranzas) — «retail con crédito propio», «mutualistas»—
    siempre iguales sin importar el producto. Con IA, el perfil se deduce
    del texto real, y los textos vuelven en los TRES idiomas porque entran
    a los correos."""
    import json as jsonmod

    from cliente_ia.proveedores.demo import ProveedorDemo
    from cliente_ia.proveedores.llm import ProveedorLLM

    empresa = ProveedorDemo("es").investigar("mvsqlnlp.com")
    empresa.resumen_sitio = "Preguntale a tu base de datos en lenguaje natural."
    catalogo = list(empresa.sectores_objetivo)

    respuesta = jsonmod.dumps({
        "categoria": "Text-to-SQL para equipos de datos",
        "tamano_objetivo": "50-5000 empleados",
        "sectores_objetivo": ["Fintech y banca digital", "E-commerce",
                              "Consultoras de datos", "SaaS B2B"],
        "textos": {
            "es": {"propuesta": "traduce preguntas en español a SQL validado",
                   "dolores": ["el equipo espera días por un reporte"],
                   "diferenciales": ["valida contra el esquema real"]},
            "pt": {"propuesta": "traduz perguntas em português para SQL validado",
                   "dolores": ["a equipe espera dias por um relatório"],
                   "diferenciales": ["valida contra o esquema real"]},
            "en": {"propuesta": "turns plain questions into validated SQL",
                   "dolores": ["the team waits days for a report"],
                   "diferenciales": ["validates against the real schema"]},
        },
    })
    monkeypatch.setattr(ProveedorLLM, "_pedir", lambda self, p, t=8000: respuesta)

    llm = ProveedorLLM(clave="sk-x", proveedor="openai")
    perfilada = llm.perfilar(empresa)

    assert perfilada.categoria == "Text-to-SQL para equipos de datos"
    assert perfilada.sectores_objetivo != catalogo
    assert "Fintech y banca digital" in perfilada.sectores_objetivo
    # Nada del catálogo de cobranzas sobrevive en el nicho.
    assert not any("crédito propio" in s or "mutualistas" in s.lower()
                   for s in perfilada.sectores_objetivo)
    # Los tres idiomas, completos: es lo que exige la fase 6.
    for idioma in ("es", "pt", "en"):
        assert perfilada.textos[idioma]["propuesta"]
        assert perfilada.textos[idioma]["dolores"]
        assert perfilada.textos[idioma]["diferenciales"]
    assert "SQL" in perfilada.textos["pt"]["propuesta"]
    assert "relatório" in perfilada.textos["pt"]["dolores"][0]
    # El nombre no se escribe dos veces seguidas en la propuesta.
    assert perfilada.propuesta.count(perfilada.nombre) == 1


def test_sin_sectores_el_perfil_del_catalogo_queda_intacto(monkeypatch):
    """Medio perfil es peor que el del catálogo: si el modelo no devuelve
    sectores, se levanta el error (la cadena lo convierte en aviso) y la
    fase 1 sigue con lo que ya tenía."""
    from cliente_ia.proveedores.demo import ProveedorDemo
    from cliente_ia.proveedores.llm import ErrorLLM, ProveedorLLM

    empresa = ProveedorDemo("es").investigar("mvsqlnlp.com")
    monkeypatch.setattr(ProveedorLLM, "_pedir",
                        lambda self, p, t=8000: '{"categoria": "Algo"}')
    llm = ProveedorLLM(clave="sk-x", proveedor="openai")
    try:
        llm.perfilar(empresa)
    except ErrorLLM as e:
        assert "sectores" in str(e)
    else:
        raise AssertionError("sin sectores tenía que fallar")


def test_claude_funciona_sin_el_sdk_instalado(monkeypatch):
    """La app de PC no empaqueta `anthropic` (son decenas de MB): sin el SDK,
    Claude tiene que salir igual por la API de mensajes vía REST, o una clave
    de Claude pegada en el escritorio no serviría para nada."""
    import builtins

    from cliente_ia.proveedores.llm import ProveedorLLM

    real_import = builtins.__import__

    def sin_anthropic(nombre, *a, **k):
        if nombre == "anthropic":
            raise ImportError("no instalado")
        return real_import(nombre, *a, **k)

    monkeypatch.setattr(builtins, "__import__", sin_anthropic)

    visto = {}

    def post_falso(self, url, cuerpo, cabeceras):
        visto.update(url=url, cuerpo=cuerpo, cabeceras=cabeceras)
        return {"content": [{"type": "text", "text": "[]"}], "stop_reason": "end_turn"}

    monkeypatch.setattr(ProveedorLLM, "_post_json", post_falso)
    p = ProveedorLLM(clave="sk-ant-x", proveedor="claude")
    assert p._pedir("hola", 8000) == "[]"
    assert visto["url"] == "https://api.anthropic.com/v1/messages"
    assert visto["cabeceras"]["x-api-key"] == "sk-ant-x"
    assert visto["cabeceras"]["anthropic-version"]      # sin versión, 400
    assert visto["cuerpo"]["max_tokens"] == 8000


def test_sin_presupuesto_de_tiempo_no_llega_a_llamar_al_proveedor():
    """Serverless: si ya no queda presupuesto (Vercel igual va a cortar la
    conexión a los 300s), `_pedir` corta ANTES de llamar — nunca debería
    intentar un pedido que de movida no puede empezar a tiempo."""
    from cliente_ia.proveedores.llm import ErrorLLM, ProveedorLLM

    p = ProveedorLLM(clave="sk-ant-x", proveedor="claude", presupuesto=0.01)
    time.sleep(0.02)                                     # se vence el presupuesto

    def _no_debería_llamarse(*args, **kwargs):
        raise AssertionError("se llamó al proveedor sin presupuesto de tiempo")

    p._pedir_una_vez = _no_debería_llamarse
    try:
        p._pedir("hola")
    except ErrorLLM as e:
        assert "tiempo" in str(e).lower()
    else:
        raise AssertionError("sin presupuesto tenía que cortar con ErrorLLM")


def test_no_reintenta_si_el_presupuesto_no_alcanza_para_otro_intento(monkeypatch):
    """Un timeout normalmente se reintenta una vez (ver `_pedir`), pero un
    reintento que de por sí no puede terminar antes del presupuesto es
    tiempo tirado: mejor cortar con un error claro que dejar que Vercel mate
    la conexión sin avisar."""
    from cliente_ia.proveedores.llm import TIMEOUT, ErrorLLM, ProveedorLLM

    # Presupuesto mayor a 0 (deja arrancar el primer intento) pero menor al
    # TIMEOUT (no alcanza para un reintento completo).
    p = ProveedorLLM(clave="sk-ant-x", proveedor="claude", presupuesto=TIMEOUT / 2)

    llamadas = []

    def _siempre_timeout(*args, **kwargs):
        llamadas.append(1)
        raise TimeoutError("se colgó")

    p._pedir_una_vez = _siempre_timeout
    try:
        p._pedir("hola")
    except ErrorLLM as e:
        assert len(llamadas) == 1, "no tenía que reintentar sin presupuesto para terminar"
        assert "presupuesto" in str(e).lower()
    else:
        raise AssertionError("sin presupuesto para reintentar tenía que cortar con ErrorLLM")


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


class _RespuestaFalsa:
    """Un `with urllib.request.urlopen(...) as r: json.load(r)` sin red:
    basta con `.read()` devolviendo los bytes del JSON."""

    def __init__(self, payload):
        import json
        self._payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._payload


def test_listar_modelos_trae_los_de_cada_proveedor(monkeypatch):
    """El botón «Actualizar» de Configuración: cada proveedor devuelve sus
    modelos en una forma distinta, y acá se homogeneizan a una lista plana
    de nombres. Gemini de paso saca lo que no sirve para chat (embeddings)."""
    from cliente_ia.proveedores.llm import ErrorLLM, listar_modelos

    respuestas = {
        "claude": {"data": [{"id": "claude-opus-5"}, {"id": "claude-haiku-4-5"}]},
        "openai": {"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]},
        "grok": {"data": [{"id": "grok-4"}]},
        "gemini": {"models": [
            {"name": "models/gemini-2.5-flash",
             "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/embedding-001",
             "supportedGenerationMethods": ["embedContent"]},
        ]},
    }
    esperado = {
        "claude": ["claude-haiku-4-5", "claude-opus-5"],
        "openai": ["gpt-4o", "gpt-4o-mini"],
        "grok": ["grok-4"],
        "gemini": ["gemini-2.5-flash"],
    }
    for proveedor, payload in respuestas.items():
        monkeypatch.setattr("urllib.request.urlopen",
                            lambda *a, _p=payload, **k: _RespuestaFalsa(_p))
        assert listar_modelos(proveedor, "clave-de-prueba") == esperado[proveedor]

    # Copilot no tiene lista: el modelo lo fija el deployment de Azure.
    try:
        listar_modelos("copilot", "clave-de-prueba")
    except ErrorLLM as e:
        assert "modelo se escribe a mano" in str(e)
    else:
        raise AssertionError("copilot no debería tener lista de modelos")

    # Sin clave no hay nada que preguntar.
    try:
        listar_modelos("claude", "")
    except ErrorLLM as e:
        assert "clave" in str(e).lower()
    else:
        raise AssertionError("sin clave tenía que fallar")


def test_listar_modelos_no_repite_la_clave_en_el_error(monkeypatch):
    import io
    import urllib.error

    from cliente_ia.proveedores.llm import ErrorLLM, listar_modelos

    def _falla_401(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://api.openai.com/v1/models", 401, "Unauthorized", {},
            io.BytesIO(b'{"error": "bad key: sk-super-secreta-123"}'))

    monkeypatch.setattr("urllib.request.urlopen", _falla_401)
    try:
        listar_modelos("openai", "sk-super-secreta-123")
    except ErrorLLM as e:
        assert "sk-super-secreta-123" not in str(e)
        assert "401" in str(e)
    else:
        raise AssertionError("el 401 tenía que propagarse como ErrorLLM")


def test_mercado_solo_mi_pais_llena_el_cupo_con_locales():
    """El filtro «sólo mi país» renormaliza el reparto: la ola local se lleva
    el límite entero, no el 45% que le tocaba cuando estaban las tres olas."""
    c = pipeline.ejecutar("mvkobranzaia.com", modo="demo",
                          limite_prospectos=20, mercado="local")
    assert c.estado == "listo"
    assert c.mercado == "local"
    assert len(c.prospectos) == 20
    assert all(p.nivel == "local" for p in c.prospectos)
    assert all(p.pais == "UY" for p in c.prospectos)


def test_mercado_solo_mi_region():
    c = pipeline.ejecutar("mvkobranzaia.com", modo="demo",
                          limite_prospectos=20, mercado="regional")
    assert c.estado == "listo"
    assert all(p.nivel == geo.NIVEL_REGIONAL for p in c.prospectos)


def test_el_nombre_viejo_del_filtro_sigue_andando():
    """Un navegador con «latam» guardado del filtro anterior no puede recibir
    un 422: se traduce a la ola regional."""
    c = pipeline.ejecutar("mvkobranzaia.com", modo="demo",
                          limite_prospectos=20, mercado="latam")
    assert c.estado == "listo"
    assert c.mercado == geo.NIVEL_REGIONAL
    assert all(p.nivel == geo.NIVEL_REGIONAL for p in c.prospectos)


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


def test_un_resultado_verificado_no_se_muestra_como_fallo_con_datos_sinteticos():
    """Lo que la pantalla mostraba mal, y es lo peor que puede decir el producto.

    Todos los avisos iban abajo de UN cartel que decía «algunas fases con IA
    fallaron y se cubrieron con datos sintéticos». Ahí adentro caían cosas que
    no eran ni un fallo ni datos sintéticos —que ningún competidor tuviera base
    en el mercado elegido, que es el filtro informando— y hasta resultados
    buenos: «Contactos públicos: 23 de 50 empresas REALES publican correo».

    O sea que el programa se acusaba de haber fallado y declaraba sintéticos
    datos reales que él mismo acababa de verificar. Rompía la regla del
    proyecto en los dos sentidos a la vez: lo sintético se dice sintético, y lo
    real no se declara falso.
    """
    from cliente_ia import modelos

    c = modelos.Corrida(id="x", dominio="mvkobranzaia.com")
    c.avisos = [
        modelos.Aviso("openai · competencia: 429", modelos.AVISO_FALLO),
        modelos.Aviso("Ningún competidor conocido tiene base en el mercado "
                      "elegido (Uruguay); se muestran los de todos lados.",
                      modelos.AVISO_AJUSTE),
        modelos.Aviso("Contactos públicos: 23 de 50 empresas reales publican "
                      "correo, teléfono o redes en su sitio.",
                      modelos.AVISO_DATO),
    ]
    por_tipo = {a.tipo for a in c.avisos}
    assert por_tipo == {"fallo", "ajuste", "dato"}, (
        "los tres tienen que quedar en grupos distintos: la interfaz los pinta "
        "bajo carteles distintos y ahí está todo el arreglo")

    # Y la clase tiene que sobrevivir al disco: si se pierde al guardar, la
    # corrida reabierta vuelve a mostrar el cartel equivocado.
    leida = modelos.desde_dict(c.a_dict())
    assert [a.tipo for a in leida.avisos] == ["fallo", "ajuste", "dato"]
    assert "Contactos públicos" in leida.avisos[2]
    assert leida.avisos[2].tipo == modelos.AVISO_DATO


def test_una_corrida_guardada_antes_de_los_tipos_se_sigue_leyendo():
    """Las corridas viejas guardaron strings pelados. Se leen como el tipo
    neutro: no se las acusa de haber fallado ni se les inventa un resultado."""
    from cliente_ia import modelos

    vieja = modelos.desde_dict(
        {"id": "v1", "dominio": "d.com", "avisos": ["algo que pasó"]})
    assert len(vieja.avisos) == 1
    assert vieja.avisos[0] == "algo que pasó"
    assert vieja.avisos[0].tipo == modelos.AVISO_AJUSTE


def test_el_filtro_de_mercado_no_es_un_fallo_de_la_ia(monkeypatch):
    """El caso exacto de la pantalla: mercado «sólo Uruguay», ningún
    competidor con base ahí. Es el filtro haciendo su trabajo y contándolo, no
    una fase que se cayó — así que no puede salir bajo el cartel de fallos."""
    from cliente_ia import modelos, pipeline

    c = pipeline.ejecutar("mvkobranzaia.com", modo="demo", mercado="local",
                          pais_base="UY", limite_prospectos=5, limite_emails=2)
    for a in c.avisos:
        if "mercado" in a.lower() or "competidor" in a.lower():
            assert a.tipo != modelos.AVISO_FALLO, (
                f"«{a}» se está mostrando como un fallo con datos sintéticos")


def test_un_competidor_que_vende_en_mi_mercado_no_se_cae_por_no_tener_base_ahi():
    """El caso exacto de la pantalla: mvkobranzaia.com, mercado «sólo Uruguay».

    La fase 2 traía yalo.com (México) y zenvia.com (Brasil) — que le venden a
    clientes uruguayos y por lo tanto SÍ le compiten a un uruguayo. El
    proveedor de IA ya los había conservado a propósito («los de casa MÁS los
    de afuera que venden acá»), pero el pipeline volvía a filtrar por país de
    BASE y los tiraba a los dos. Resultado: la lista quedaba vacía, saltaba
    «ningún competidor tiene base en el mercado elegido; se muestran los de
    todos lados» y terminaba mostrando a TODOS —incluidos los que no venden
    ahí— o sea lo contrario de lo que pedía el filtro.
    """
    from cliente_ia import geo, modelos, pipeline

    def _comp(dominio, pais, vende):
        return modelos.Competidor(dominio=dominio, pais=pais,
                                  vende_en_objetivo=vende, solapamiento=0.8)

    competidores = [
        _comp("yalo.com", "MX", True),        # base afuera, vende en UY
        _comp("zenvia.com", "BR", True),      # base afuera, vende en UY
        _comp("lejano.com", "JP", False),     # ni base ni venta en UY
    ]
    dentro = [c for c in competidores
              if c.vende_en_objetivo or
              (c.pais and geo.nivel_de(c.pais, "UY") == geo.NIVEL_LOCAL)]

    assert [c.dominio for c in dentro] == ["yalo.com", "zenvia.com"], (
        "los que venden en el mercado elegido tienen que quedar")
    assert "lejano.com" not in [c.dominio for c in dentro], (
        "el que no compite ahí no tiene por qué aparecer")
    assert pipeline is not None


def test_el_demo_sigue_recortando_por_pais_como_siempre():
    """`vende_en_objetivo` arranca en False a propósito: el proveedor demo no
    lo declara, así que su recorte por país tiene que quedar idéntico. Si el
    default fuera True, el filtro de mercado del modo demo dejaba de filtrar."""
    from cliente_ia import modelos, pipeline

    c = pipeline.ejecutar("mvkobranzaia.com", modo="demo", mercado="local",
                          pais_base="UY", limite_prospectos=5, limite_emails=2)
    assert modelos.Competidor(dominio="x.com").vende_en_objetivo is False

    # En el catálogo demo no hay competidores uruguayos, así que acá tiene que
    # verse el camino de respaldo que YA existía y no cambió: si el recorte no
    # deja ninguno se muestran todos, pero DICIÉNDOLO. Lo que no puede pasar es
    # que se muestren todos en silencio.
    del_mercado = [x for x in c.competidores
                   if x.pais == "UY" or x.vende_en_objetivo]
    if len(del_mercado) != len(c.competidores):
        assert any("competidor" in a.lower() for a in c.avisos), (
            "se mostraron competidores de afuera del mercado elegido sin avisar")
        # Y ese aviso es del filtro informando, no un fallo con datos sintéticos.
        for a in c.avisos:
            if "competidor" in a.lower():
                assert a.tipo != modelos.AVISO_FALLO


def test_vender_en_el_mercado_no_se_presume_se_afirma():
    """`vende_en_objetivo` omitido por el modelo NO es un sí. Con el default
    en True, elegir «sólo mi país» no filtraba nada: todo competidor
    extranjero pasaba por un campo que nadie había afirmado — la pantalla
    mostraba US/MX/BR bajo «Sólo Uruguay» sin una línea de por qué."""
    import json as _json

    from cliente_ia.modelos import Empresa
    from cliente_ia.proveedores.llm import ProveedorLLM

    p = ProveedorLLM.__new__(ProveedorLLM)
    p.proveedor, p.nombre, p.idioma_base = "claude", "claude", "es"
    p.mercado, p.pais_base, p.notas = "local", "UY", []
    respuesta = _json.dumps([
        {"dominio": "concasa.com.uy", "nombre": "ConCasa", "pais": "UY",
         "vende_en_objetivo": True, "solapamiento": 0.8},
        {"dominio": "vendeahi.com", "nombre": "VendeAhí", "pais": "MX",
         "vende_en_objetivo": True, "solapamiento": 0.7},
        {"dominio": "sindecir.com", "nombre": "SinDecir", "pais": "US",
         "solapamiento": 0.9},                      # sin el campo: no afirmó
        {"dominio": "novende.com", "nombre": "NoVende", "pais": "BR",
         "vende_en_objetivo": False, "solapamiento": 0.9},
    ])
    p._pedir = lambda prompt, max_tokens: respuesta
    p._verificar_competencia = lambda comps, emp: comps   # sin red en el test
    p._competencia_local = lambda emp, paises: []

    quedaron = [c.dominio for c in p.competencia(Empresa(dominio="mi.com", pais="UY"))]
    assert "concasa.com.uy" in quedaron          # base en el mercado
    assert "vendeahi.com" in quedaron            # afirmó que vende ahí
    assert "sindecir.com" not in quedaron        # no afirmó: no pasa
    assert "novende.com" not in quedaron         # dijo que no vende ahí


def test_un_competidor_medido_como_rubro_distinto_no_se_muestra(monkeypatch):
    """La captura del dueño: yalo.ai etiquetado «RUBRO DISTINTO» por el propio
    motor… y en la lista igual. Si la medición dio otro rubro y la lista
    aguanta el descuento, se descarta y se dice; con la lista corta se
    conserva etiquetado (una portada que es pura imagen también mide bajo)."""
    from cliente_ia import modelos, segmento
    from cliente_ia.modelos import Competidor, Empresa
    from cliente_ia.proveedores.llm import ProveedorLLM

    p = ProveedorLLM.__new__(ProveedorLLM)
    p.nombre, p.notas = "claude", []
    monkeypatch.setattr(segmento, "huella_verificable",
                        lambda emp: segmento.Huella({"cobranza": 1.0}))

    afinidades = {"bueno1.com": 0.5, "bueno2.com": 0.4, "bueno3.com": 0.35,
                  "distinto.com": 0.10,   # entre AJENA (0.06) y DUDOSA (0.15)
                  "ajeno.com": 0.01}

    def _bajar_falso(dominio, timeout):
        return f"html de {dominio}"

    monkeypatch.setattr("cliente_ia.proveedores.web.bajar", _bajar_falso)
    monkeypatch.setattr(segmento, "afinidad_de_html",
                        lambda huella, html: afinidades[html.split()[-1]])

    lista = [Competidor(dominio=d, solapamiento=0.6) for d in afinidades]
    quedan = {c.dominio for c in p._verificar_competencia(
        lista, Empresa(dominio="mi.com"))}
    assert "ajeno.com" not in quedan
    assert "distinto.com" not in quedan, "medido como otro rubro y mostrado igual"
    assert {"bueno1.com", "bueno2.com", "bueno3.com"} <= quedan
    assert any(a.tipo == modelos.AVISO_DATO for a in p.notas)

    # Lista corta: el «rubro distinto» se CONSERVA (etiquetado) — descartar
    # con dos competidores en pie vacía la fase por una medición dudosa.
    p.notas = []
    corta = [Competidor(dominio=d, solapamiento=0.6)
             for d in ("bueno1.com", "distinto.com")]
    quedan_corta = {c.dominio for c in p._verificar_competencia(
        corta, Empresa(dominio="mi.com"))}
    assert "distinto.com" in quedan_corta


def test_los_decisores_reales_llevan_los_cargos_de_su_campana():
    """A un banco no le firman la compra un «Head of Growth» y un «VP of
    Sales». Con prospectos de la IA, el sector es texto libre que no coincidía
    con los nombres EXACTOS del catálogo, todo caía al fallback de saas_b2b y
    los cargos salían de otro rubro. Ahora mandan los cargos que la campaña
    dedujo del producto real, y sin ellos el sector se matchea por parecido."""
    from cliente_ia.modelos import Prospecto
    from cliente_ia.proveedores.demo import ProveedorDemo

    demo = ProveedorDemo("es")

    con_cargos = Prospecto(
        id="p0001", nombre="Banco Ejemplo S.A.", dominio="bancoejemplo.com.uy",
        sector="Bancos privados y financieras", pais="UY", nivel="local",
        prioridad=1, idioma="es", sintetico=False, fuente="llm",
        cargos_decisor=["Gerente de Cobranzas", "Director de Riesgo"])
    decisores = demo.decisores([con_cargos], 2)
    assert [d.cargo for d in decisores] == ["Gerente de Cobranzas",
                                            "Director de Riesgo"]

    # Sin cargos de campaña: el sector libre "Bancos privados…" tiene que
    # caer al sector BANCOS del catálogo por parecido, nunca a saas_b2b.
    sin_cargos = Prospecto(
        id="p0002", nombre="Banco Otro S.A.", dominio="bancootro.com.uy",
        sector="Bancos privados", pais="UY", nivel="local",
        prioridad=1, idioma="es", sintetico=False, fuente="llm")
    cargos_banco = set(demo.datos["sectores"]["bancos"]["cargos"])
    for d in demo.decisores([sin_cargos], 3):
        assert d.cargo in cargos_banco, (
            f"«{d.cargo}» no es un cargo de banca: cayó al fallback genérico")


def test_la_busqueda_de_linkedin_no_lleva_el_sufijo_societario():
    """`Gerente de Cobranzas Banco Austral S.R.L. Uruguay` como seis palabras
    sueltas le pedía a LinkedIn cualquier homónimo. El nombre va limpio
    («Banco Austral», sin S.R.L.) y ENTRE COMILLAS, que es la frase exacta
    que una persona buscaría a mano."""
    from cliente_ia.modelos import Prospecto
    from cliente_ia.proveedores.demo import ProveedorDemo

    demo = ProveedorDemo("es")
    real = Prospecto(
        id="p0001", nombre="Banco Austral S.R.L.", dominio="bancoaustral.com.uy",
        sector="Bancos privados", pais="UY", nivel="local", prioridad=1,
        idioma="es", sintetico=False, fuente="llm")
    d = demo.decisores([real], 1)[0]
    consulta = urllib.parse.unquote(d.linkedin)
    assert '"Banco Austral"' in consulta
    assert "S.R.L" not in consulta
    assert "Uruguay" in consulta          # el país sigue acotando homónimos


def test_la_consulta_de_decisores_usa_los_cargos_de_la_campana():
    """La búsqueda de gente de LinkedIn buscaba `director OR gerente OR jefe`
    para cualquier producto: matchea a cualquier jefe de cualquier rubro. Con
    los cargos que la campaña dedujo del producto real, busca ESOS puestos."""
    from cliente_ia import busqueda_social, segmento

    huella = segmento.Huella({"cobranza": 1.0, "mora": 0.5})
    con = busqueda_social.para_segmento(
        huella, sector="bancos", pais="UY", idioma="es",
        cargos=["Gerente de Cobranzas", "Director de Riesgo"])
    gente = next(b for b in con if b.etiqueta == "decisores")
    assert '"Gerente de Cobranzas" OR "Director de Riesgo"' in gente.consulta

    sin = busqueda_social.para_segmento(huella, sector="bancos", pais="UY",
                                        idioma="es")
    gente_sin = next(b for b in sin if b.etiqueta == "decisores")
    assert "director OR gerente" in gente_sin.consulta   # el genérico de siempre


def test_un_prospecto_medido_como_de_otro_rubro_se_cae_de_la_lista(monkeypatch):
    """Reordenar no alcanzaba: la empresa de otro rubro quedaba al final de la
    lista… pero en la lista. Medida como claramente ajena, se descarta y se
    avisa cuántas se cayeron — salvo que TODO lo medido dé ajeno, que es señal
    de huella pobre y no de lista mala."""
    from cliente_ia import modelos, pipeline, segmento

    def _enriquecer_falso(prospectos, huella=None):
        for i, p in enumerate(prospectos):
            p.afinidad = 0.01 if i < 2 else 0.5   # dos claramente ajenos
        return (3, len(prospectos))

    monkeypatch.setattr("cliente_ia.proveedores.contactos.enriquecer",
                        _enriquecer_falso)
    c = pipeline.ejecutar("mvkobranzaia.com", modo="demo",
                          limite_prospectos=8, limite_emails=2)
    assert all(p.afinidad >= segmento.AFIN_AJENA for p in c.prospectos)
    assert len(c.prospectos) == 6
    caida = next(a for a in c.avisos if "descartaron" in a and "rubro" in a)
    assert caida.tipo == modelos.AVISO_DATO
