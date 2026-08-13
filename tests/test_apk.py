"""
El APK y las tres formas de instalarlo en el celular.

Sigue la metodología de MV Agendate IA: APK release firmado con clave propia,
guía de instalación con verificación de integridad, y la vía sin instalar nada
(«agregar a pantalla de inicio»).

Lo que se puede probar desde acá es la configuración y los documentos. Que el
APK compile, quede firmado y no sea depurable lo comprueba el CI con Gradle
sobre un runner con el SDK de Android (`.github/workflows/apk.yml`).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
MANIFIESTO_ANDROID = RAIZ / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
GRADLE = RAIZ / "android" / "app" / "build.gradle"
WORKFLOW = RAIZ / ".github" / "workflows" / "apk.yml"
GUIA = RAIZ / "android" / "COMO-INSTALAR.md"
MANIFIESTO_PWA = RAIZ / "webapp" / "frontend" / "public" / "manifest.webmanifest"
INDEX = RAIZ / "webapp" / "frontend" / "index.html"


# ---------------------------------------------------------------------------
# El APK que se publica
# ---------------------------------------------------------------------------
def test_el_workflow_publica_release_y_no_debug():
    """Lo que se publicaba era `assembleDebug`: `debuggable=true` y firmado
    con la clave de debug de Gradle. Con eso, cualquiera con el teléfono y
    `adb` corría `run-as` y leía el localStorage del WebView — la clave del
    modelo, la del correo y las de X y LinkedIn."""
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert "assembleRelease" in texto
    assert "assembleDebug" not in texto
    # Y el APK que se copia a la Release tiene que salir de release/
    assert "outputs/apk/release/app-release.apk" in texto
    assert "outputs/apk/debug" not in texto


def test_el_workflow_comprueba_que_el_apk_no_sea_depurable():
    """El chequeo que impide que esto vuelva a pasar en silencio."""
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert "application-debuggable" in texto


def test_el_workflow_falla_si_falta_el_keystore():
    """Sin secrets, Gradle firmaría con la clave de debug y publicaría igual.
    Preferimos que corte: un APK sin firma verificable es peor que ninguno."""
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert "ANDROID_KEYSTORE_BASE64" in texto
    assert "::error::" in texto
    assert "armar_keystore.sh" in GUIA.read_text(encoding="utf-8")


def test_el_gradle_no_deja_el_release_depurable_ni_sin_firmar():
    texto = GRADLE.read_text(encoding="utf-8")
    assert "debuggable false" in texto
    assert "signingConfigs" in texto
    # La firma sale del entorno, nunca de un keystore versionado.
    assert "System.getenv" in texto
    assert not list(RAIZ.glob("**/*.jks")), "hay un keystore versionado"
    assert not list(RAIZ.glob("**/*.keystore")), "hay un keystore versionado"


def test_el_apk_no_respalda_ni_deja_leer_lo_que_guarda():
    """`allowBackup` mandaba el localStorage del WebView —con todas las
    claves del usuario— a la nube y a `adb backup`."""
    texto = MANIFIESTO_ANDROID.read_text(encoding="utf-8")
    assert 'android:allowBackup="false"' in texto
    assert 'android:networkSecurityConfig="@xml/seguridad_red"' in texto


@pytest.mark.parametrize("archivo", [
    "android/app/src/main/res/xml/seguridad_red.xml",
    "android/app/src/main/res/xml/reglas_respaldo.xml",
])
def test_los_xml_de_seguridad_existen_y_parsean(archivo):
    import xml.etree.ElementTree as ET
    ET.parse(RAIZ / archivo)


def test_el_texto_plano_solo_se_permite_en_redes_privadas():
    """El APK apunta a un servidor propio en la LAN, así que el HTTP hace
    falta — pero sólo ahí. Contra internet, HTTPS obligatorio: si no, las
    claves del usuario viajan a la vista de cualquiera en el mismo wifi."""
    texto = (RAIZ / "android/app/src/main/res/xml/seguridad_red.xml").read_text(encoding="utf-8")
    assert 'cleartextTrafficPermitted="false"' in texto      # el default
    assert "192.168" in texto and "10.0.0.0" in texto        # la excepción
    cfg = json.loads((RAIZ / "capacitor.config.json").read_text(encoding="utf-8"))
    assert "cleartext" not in cfg.get("server", {}), \
        "capacitor.config.json vuelve a habilitar texto plano para TODO destino"
    assert cfg["android"]["allowMixedContent"] is False


# ---------------------------------------------------------------------------
# Las tres formas de instalarlo
# ---------------------------------------------------------------------------
def test_la_guia_cubre_las_tres_vias():
    texto = GUIA.read_text(encoding="utf-8").lower()
    assert "sin instalar nada" in texto              # 1: navegador
    assert "pantalla" in texto and "inicio" in texto  # 2: PWA
    assert ".apk" in texto                           # 3: APK
    # Y lo que hace que una descarga sea verificable.
    assert "sha256" in texto
    assert "aplicaci" in texto and "no instalada" in texto   # el error clásico


def test_la_guia_explica_que_la_edicion_la_pone_el_servidor():
    """El APK no lleva motor: pregunta la licencia al servidor
    (`GET /api/licencia`). Por eso no necesita conversor a edición dueño —
    hereda la del servidor al que apunta."""
    # El markdown corta las líneas a 79 columnas, así que una frase puede
    # quedar partida al medio: se normalizan los espacios antes de buscarla.
    texto = re.sub(r"\s+", " ", GUIA.read_text(encoding="utf-8")).lower()
    assert "/api/licencia" in texto
    assert "no hace falta ningún conversor para el apk" in texto


def test_el_manifiesto_pwa_es_valido_y_esta_enganchado():
    """La vía «sin instalar nada» de Agendate: agregar a pantalla de inicio.
    Sin manifest queda un acceso directo del navegador, con barra de
    direcciones y sin ícono propio."""
    m = json.loads(MANIFIESTO_PWA.read_text(encoding="utf-8"))
    assert m["name"] and m["short_name"]
    assert m["display"] == "standalone"
    assert m["icons"] and all(i["src"] and i["sizes"] for i in m["icons"])
    # Rutas relativas: la app se sirve tanto en / (instalada) como en /app/
    # (la web), y una ruta absoluta rompería una de las dos.
    assert m["start_url"].startswith("./") and m["scope"].startswith("./")
    for icono in m["icons"]:
        assert icono["src"].startswith("./")
        assert (RAIZ / "webapp" / "frontend" / "public" / icono["src"][2:]).exists()

    html = INDEX.read_text(encoding="utf-8")
    assert 'rel="manifest"' in html
    assert "apple-touch-icon" in html


def test_el_generador_de_keystore_avisa_que_no_se_puede_perder():
    """Si se pierde el keystore, ninguna actualización se instala encima de
    lo ya instalado. No hay forma de recuperarlo, así que el aviso tiene que
    estar donde se lo lee."""
    guion = (RAIZ / "packaging" / "armar_keystore.sh").read_text(encoding="utf-8")
    assert "GUARDA" in guion.upper()
    assert "RSA" in guion and "4096" in guion
    # No pisa un keystore existente: hacerlo dejaría la app sin actualizar.
    assert "ya existe" in guion
    assert "ANDROID_KEYSTORE_BASE64" in guion


def test_el_workflow_del_apk_no_interpola_en_el_run():
    """`${{ }}` se expande como TEXTO antes de que exista el shell."""
    datos = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in datos["jobs"].values():
        for paso in job.get("steps", []):
            run = paso.get("run")
            if run and "${{" in run:
                # Sólo se admite dentro de `env:`, no en el cuerpo del script.
                encontrados = re.findall(r"\$\{\{[^}]+\}\}", run)
                raise AssertionError(
                    f"paso '{paso.get('name')}' interpola en el run: {encontrados}")
