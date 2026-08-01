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
