"""Que el programa se instale donde el usuario quiera, y que el APK conecte.

Dos bugs concretos que estos tests impiden que vuelvan:

1. **El instalador obligaba a usar C:.** El instalador asistido de
   electron-builder muestra la pantalla "¿para quién instalar?" y la opción
   "para todos los usuarios" pide UAC e instala en `C:\\Program Files` — una
   carpeta que el usuario NO puede escribir, así que `dirDatos()` cae a
   `%LOCALAPPDATA%` y el programa entero queda en C: aunque el usuario hubiera
   querido otro disco.
2. **El APK no conectaba con NINGÚN servidor.** La app vive en
   `https://localhost` (androidScheme) y el uso normal es apuntarla a la PC del
   usuario por `http://192.168.x.x`. Eso es contenido mixto y el WebView de
   Android lo bloquea por defecto; Capacitor sólo lo habilita con
   `allowMixedContent`. Estaba en `false`: fallaba con un error de red genérico.
3. **Con el servidor mal configurado, el APK MENTÍA que se había conectado.**
   Con la dirección vacía, `fetch("" + ruta)` es relativa a `https://localhost`
   — el propio origen del bundle. El servidor local de Capacitor está en
   "html5mode" (rutea cualquier ruta sin extensión a `index.html`, para que el
   router de una sola página ande en `/#/...`), así que `GET /api/salud`
   devolvía el HTML de la app con status 200 en vez de un error de red.
   `r.json()` fallaba en silencio (hay un `.catch(() => ({}))` a propósito,
   para no romper con una respuesta vacía) y `api()` devolvía `{}` como si el
   pedido hubiera funcionado: "Conexión correcta · vundefined" en pantalla,
   sin haber hablado con ningún servidor. Se vio en un celular real.
"""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ELECTRON = RAIZ / "electron"
MAIN_JS = ELECTRON / "main.js"
INSTALLER_NSH = ELECTRON / "build" / "installer.nsh"


def _nsis() -> dict:
    return json.loads((ELECTRON / "package.json").read_text(encoding="utf-8"))["build"]["nsis"]


# --- el instalador de Windows -----------------------------------------------

def test_el_instalador_deja_elegir_la_carpeta():
    """La única decisión que importa: en qué carpeta y en qué disco."""
    n = _nsis()
    assert n["allowToChangeInstallationDirectory"] is True
    # `oneClick` tiene que seguir en false: con true no hay página de directorio
    # (electron-builder directamente rechaza la combinación).
    assert n["oneClick"] is False


def test_el_instalador_no_ofrece_la_via_que_termina_en_program_files():
    """`perMachine` y la elevación apagadas, y el macro que saltea la pantalla.

    Los tres tienen que estar: sin `installer.nsh` la pantalla aparece igual y
    el usuario puede elegir la opción que lo manda a C:.
    """
    n = _nsis()
    assert n["perMachine"] is False
    assert n["allowElevation"] is False, (
        "con la elevación habilitada el instalador puede pedir UAC e instalar "
        "en Archivos de programa")
    assert n.get("include") == "build/installer.nsh"

    fuente = INSTALLER_NSH.read_text(encoding="utf-8")
    assert "!macro customInstallMode" in fuente
    assert 'StrCpy $isForceCurrentInstall "1"' in fuente, (
        "sin forzar la instalación por usuario vuelve la pantalla que lleva a "
        "C:\\Program Files")


def test_el_perfil_del_webview_acompana_a_la_app():
    """Elegir el disco tiene que valer para TODO.

    Las corridas ya iban al lado de la app, pero el perfil de Chromium —donde
    viven la licencia y las claves de IA, SMTP, X y LinkedIn— se iba a %APPDATA%
    igual: instalar en D: dejaba media app en C:.
    """
    fuente = MAIN_JS.read_text(encoding="utf-8")
    assert "perfilJuntoALaApp" in fuente
    assert 'app.setPath("userData"' in fuente

    # Se llama ANTES de whenReady: después, Chromium ya abrió el perfil y
    # setPath no tiene efecto. Se busca la LLAMADA (`.then(`), no la mención:
    # el docstring de la función también nombra a `app.whenReady()` y la
    # primera versión de este test comparaba contra ese comentario.
    assert fuente.index("perfilJuntoALaApp();") < fuente.index("app.whenReady().then(")

    bloque = fuente.split("function perfilJuntoALaApp()", 1)[1].split("\n}", 1)[0]
    # Copia, no mueve: si la migración falla, la configuración vieja sigue ahí.
    assert "cpSync" in bloque and "renameSync" not in bloque
    # Y no se muda a una carpeta que no se puede escribir.
    assert "if (!dir) return" in bloque


def test_no_se_copia_el_cache_de_chromium_al_migrar():
    """Un perfil con caché pesa cientos de megas y el caché se regenera solo."""
    fuente = MAIN_JS.read_text(encoding="utf-8")
    assert "CACHES" in fuente
    for carpeta in ("Cache", "Code Cache", "GPUCache", "Crashpad"):
        assert f'"{carpeta}"' in fuente, f"{carpeta} tendría que estar en CACHES"


def test_los_recursos_del_instalador_viajan_en_el_repo():
    """El arreglo más silencioso de todos.

    `.gitignore` tenía `build/` sin barra adelante, y ese patrón matchea
    CUALQUIER carpeta llamada `build` a cualquier profundidad — incluida
    `electron/build/`, que no es salida de nada: son los recursos del
    instalador. Resultado: `icon.ico` e `icon.png` nunca estuvieron en el repo
    y el CI armaba el instalador y la app con el icono por defecto de Electron.
    Nadie lo notó porque los dos .bmp del panel lateral sí estaban (alguien los
    forzó en su momento) y el build no falla por un icono faltante: lo
    reemplaza.
    """
    import subprocess

    faltan = [
        n for n in ("icon.ico", "icon.png", "installer.nsh",
                    "installerSidebar.bmp", "uninstallerSidebar.bmp")
        if subprocess.run(["git", "check-ignore", "-q", f"electron/build/{n}"],
                          cwd=RAIZ, check=False).returncode == 0
    ]
    assert not faltan, (
        f"El .gitignore está ignorando recursos del instalador: {faltan}. "
        "Revisá que la regla de `build/` esté anclada a la raíz (`/build/`).")

    for n in ("icon.ico", "icon.png", "installer.nsh"):
        assert (ELECTRON / "build" / n).exists(), f"falta electron/build/{n}"


# --- el APK ------------------------------------------------------------------

def _capacitor() -> dict:
    return json.loads((RAIZ / "capacitor.config.json").read_text(encoding="utf-8"))


def test_el_apk_puede_hablar_con_un_servidor_de_la_lan():
    """El bug: la app corre en https://localhost y el servidor del usuario es
    http://192.168.x.x. Sin esto el WebView bloquea el pedido y el APK no sirve
    para nada — que es su único modo de uso."""
    cfg = _capacitor()
    assert cfg["android"]["allowMixedContent"] is True, (
        "sin esto el WebView bloquea todo http:// desde la página https y el "
        "APK no puede conectarse a ningún servidor de la LAN")


def test_las_tres_capas_del_texto_plano_estan_de_acuerdo():
    """Regresión de coherencia: las tres capas tienen que decir lo mismo, o el
    APK falla en la que quedó cerrada sin que nadie lo note.

      1. Network Security Config → permite texto plano
      2. Capacitor / WebView     → permite contenido mixto
      3. la app (api.js)         → SÓLO loopback y RFC 1918
    """
    nsc = (RAIZ / "android/app/src/main/res/xml/seguridad_red.xml").read_text(encoding="utf-8")
    assert 'cleartextTrafficPermitted="true"' in nsc

    assert _capacitor()["android"]["allowMixedContent"] is True

    api = (RAIZ / "webapp/frontend/src/api.js").read_text(encoding="utf-8")
    bloque = api.split("export function baseInsegura", 1)[1].split("\n}", 1)[0]
    # El candado REAL: el WebView no sabe distinguir una LAN de internet, la app sí.
    for red in (r"192\.168", r"10\.", r"127\."):
        assert red in bloque, f"baseInsegura dejó de reconocer {red}"
    assert "https" in bloque


def test_el_apk_sigue_sin_permitir_texto_plano_a_internet():
    """Abrir el contenido mixto en el WebView no puede haber abierto la puerta
    a mandar las claves del usuario en texto plano a un host público."""
    api = (RAIZ / "webapp/frontend/src/api.js").read_text(encoding="utf-8")
    assert "servidor_inseguro_http" in api, "se perdió el rechazo del http público"
    # Y el chequeo se hace en los DOS caminos de red, no en uno solo.
    assert api.count("baseInsegura(getBase())") >= 2, (
        "baseInsegura tiene que cortar tanto en api() como en apiStream()")


def test_sin_direccion_el_apk_no_finge_que_se_conecto():
    """El falso "Conexión correcta · vundefined".

    Con la dirección vacía, `fetch("" + ruta)` es relativa al propio origen
    del bundle (`https://localhost`). El servidor local de Capacitor está en
    "html5mode" — cualquier ruta sin extensión (incluida `/api/salud`) la
    resuelve devolviendo `index.html` con status 200, para que el router de
    una sola página ande en `/#/...`. Sin este corte, `api()` recibía ese
    HTML, `r.json()` fallaba en silencio (`.catch(() => ({}))`, a propósito
    para no romper con una respuesta vacía) y devolvía `{}` — la pantalla de
    Ajustes mostraba "conexión correcta" sin haber hablado con nada.
    """
    api = (RAIZ / "webapp/frontend/src/api.js").read_text(encoding="utf-8")
    assert "function faltaServidor()" in api
    assert "esNativo() && !getBase()" in api, (
        "faltaServidor() tiene que mirar esNativo(), no cualquier base vacía: "
        "en la web y en la app de PC una base vacía es NORMAL (relativa al "
        "propio backend)")

    # El mensaje está en los tres idiomas del producto, no sólo en español.
    bloque = api.split("const FALTA_SERVIDOR = {", 1)[1].split("};", 1)[0]
    for idioma in ("es:", "pt:", "en:"):
        assert idioma in bloque, f"falta el mensaje en {idioma[:-1]}"

    # El corte tiene que estar ANTES del fetch en los dos caminos de red, con
    # el mismo criterio que baseInsegura (que si no, corre primero y una base
    # vacía —insegura sólo para http:// contra un host público— la deja pasar
    # igual, porque "" no matchea el patrón http://).
    for firma in ("export async function api(", "export async function apiStream("):
        cuerpo = api.split(firma, 1)[1][:900]
        pos_guard = cuerpo.find("faltaServidor()")
        pos_fetch = cuerpo.find("await fetch(")
        assert pos_guard != -1, f"falta el guard en {firma}"
        assert pos_fetch != -1, f"no se encontró el fetch de {firma}"
        assert pos_guard < pos_fetch, (
            f"{firma}: el guard de faltaServidor() tiene que ir ANTES del "
            "fetch, si no el falso positivo sigue pasando")
