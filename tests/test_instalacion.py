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
import re
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


def test_el_apk_conecta_solo_sin_pedir_configuracion():
    """"quitar eso del servidor en la apk no tiene sentido" — feedback real.

    Antes, sin configurar nada, el APK quedaba mudo hasta que el usuario
    encontraba y tipeaba la IP de un servidor propio: el primer uso era una
    pantalla en rojo. Ahora `getBase()` en nativo cae a la web pública si no
    hay nada guardado — anda apenas se instala, y el campo de Ajustes sigue
    editable para quien quiera su propio servidor en la LAN.

    El dominio de ese default es `mv-cliente-ia.vercel.app`, NO
    `mvclienteia.com`: se probó con `curl` (fuera de este test, que no tiene
    red) y `mvclienteia.com` no resolvía — el dominio de marca todavía no
    está apuntado en el DNS — mientras que `mv-cliente-ia.vercel.app/api/salud`
    respondía 200. Apuntar el default ahí rompía "conecta solo" con un
    "Failed to fetch" igual de mudo que el que esto vino a arreglar. Usa el
    mismo dominio que `cliente_ia/licencia.py:URL_VALIDACION`, que ya lo
    tenía bien por la misma razón.

    `faltaServidor()` (el test de arriba) queda como red de segundo nivel:
    con este default, `getBase()` nunca vuelve a dar vacío en nativo, así que
    ese guard no debería activarse en el uso normal — pero seguir ahí no
    cuesta nada y cubre el día en que alguien rompa el default sin querer.
    """
    api = (RAIZ / "webapp/frontend/src/api.js").read_text(encoding="utf-8")
    assert "const URL_PUBLICA = " in api
    assert '"https://mv-cliente-ia.vercel.app"' in api, (
        "el default tiene que ser el dominio que de verdad resuelve — ver el "
        "docstring de este test")

    bloque = api.split("export function getBase()", 1)[1].split("\n}", 1)[0]
    assert "URL_PUBLICA" in bloque, (
        "getBase() tiene que caer a la web pública en nativo cuando no hay "
        "nada guardado, no a una cadena vacía")

    # El banner "configurá el servidor" y su corte en el catch de Explorar ya
    # no pueden disparar nunca (getBase() no vuelve a dar vacío en nativo):
    # dejarlos habría sido código muerto fingiendo una alerta que no puede
    # pasar. Se sacaron; que no vuelvan sin querer en un merge.
    explorar = (RAIZ / "webapp/frontend/src/pages/Explorar.jsx").read_text(encoding="utf-8")
    assert "aviso.sin_servidor" not in explorar

    for idioma in ("es", "pt-BR", "en"):
        d = json.loads((RAIZ / f"webapp/frontend/src/i18n/{idioma}.json")
                       .read_text(encoding="utf-8"))
        assert "sin_servidor" not in d.get("aviso", {}), (
            f"{idioma}.json: sobró la traducción de un aviso que ya no se usa")
        assert "mv-cliente-ia.vercel.app" in d["config"]["servidor_ayuda"], (
            f"{idioma}.json: la ayuda del campo no dice cuál es el default")


def test_el_bundle_publicado_no_lleva_codigo_de_dueno_horneado():
    """El APK/web que se PUBLICA no puede llevar el código de dueño adentro.

    `getOwner()` cae a `VITE_MV_OWNER`, horneado al compilar: es lo que hace
    que el APK owner abra sin límite sin configurar nada (el equivalente del
    `edicion.json` del instalador de PC). Pero el bundle de una app web es
    texto plano — cualquiera con el APK en la mano lo abre con un editor y se
    lleva el código, y con ese código le saca el cupo al servidor para
    siempre.

    Por eso el build owner sale como artifact privado de Actions y NUNCA a la
    Release, y por eso este test mira el bundle REALMENTE COMPILADO que se
    publica (`webapp/frontend/dist/` y su copia en `public/app/`): que la
    variable esté sin definir en el CI público es la intención, esto verifica
    el resultado. Si algún día alguien exporta `VITE_MV_OWNER` en el workflow
    equivocado, se entera acá y no cuando ya se bajó.
    """
    # El valor por defecto tiene que ser vacío en el fuente: si alguien
    # cablea un código acá, ningún build lo salva.
    api = (RAIZ / "webapp/frontend/src/api.js").read_text(encoding="utf-8")
    assert 'import.meta.env?.VITE_MV_OWNER || ""' in api, (
        "el código de dueño horneado tiene que caer a cadena vacía cuando no "
        "se define VITE_MV_OWNER")

    revisados = 0
    for carpeta in ("webapp/frontend/dist/assets", "public/app/assets"):
        for bundle in (RAIZ / carpeta).glob("index-*.js"):
            revisados += 1
            horneado = _codigo_de_dueno_en(bundle.read_text(encoding="utf-8"))
            assert horneado is None, (
                f"{carpeta}/{bundle.name} lleva un código de dueño horneado "
                f"({horneado[:8]}…). Ese bundle NO se puede publicar: "
                "recompilá sin VITE_MV_OWNER.")

    # Sin esto el test se vuelve un no-op en silencio el día que alguien mueva
    # `public/app/` o cambie el nombre de los bundles: cero archivos leídos, y
    # verde igual. `webapp/frontend/dist/` NO se versiona (existe sólo después
    # de compilar), así que en un checkout limpio el único que se revisa es el
    # de `public/`, que es justo el que se publica en la web.
    assert revisados, (
        "no se revisó ningún bundle: se movieron las carpetas de salida y "
        "este test dejó de mirar lo que se publica")


def _codigo_de_dueno_en(js: str) -> str | None:
    """El valor al que cae `getOwner()` en un bundle compilado, o None.

    No alcanza con buscar `getItem("mvcliente_owner")||"algo"`: Vite hoistea
    TANTO la clave como el valor a identificadores de una o dos letras, así
    que en el bundle real dice `const Vs="mvcliente_owner",Jh="CODIGO";…
    getItem(Vs)||Jh`. Una primera versión de este test buscaba el literal
    pegado y daba verde sobre un bundle envenenado a propósito — un guard que
    no guardaba nada. Hay que resolver los dos identificadores.
    """
    claves = [m.group(1) for m in
              re.finditer(r'\b([A-Za-z_$][\w$]*)\s*=\s*"mvcliente_owner"', js)]
    alternativas = "|".join([re.escape(c) for c in claves] + [r'"mvcliente_owner"'])
    uso = re.search(
        rf'getItem\(\s*(?:{alternativas})\s*\)\s*\|\|\s*([A-Za-z_$][\w$]*|"[^"]*")',
        js)
    if not uso:
        return None
    caida = uso.group(1)
    if caida.startswith('"'):                    # literal pegado ahí mismo
        return caida[1:-1] or None
    decl = re.search(rf'\b{re.escape(caida)}\s*=\s*"([^"]*)"', js)
    return (decl.group(1) or None) if decl else None


def test_los_workflows_no_tienen_claves_duplicadas():
    """`build_windows.yml` tuvo DOS bloques `env:` en el mismo paso ("Construir
    las ediciones") — uno antes del `run:` y otro después. Es YAML inválido
    ("'env' is already defined") y GitHub rechaza el workflow ENTERO antes de
    programar un solo job: ni siquiera el job barato de Linux llega a correr.

    Lo insidioso es que no se ve en ningún lado de este repo ni de la app: el
    run queda "failure" sin logs (0 jobs), así que `tests/`, `ruff` y la propia
    lista de corridas de Actions no muestran nada raro — hay que abrir el run
    en GitHub para leer el mensaje. Estuvo así varios días, publicando cero
    instaladores de Windows nuevos, sin que nada de este lado lo mostrara.

    Un YAML con una clave repetida en el MISMO mapping no es un error de
    sintaxis para PyYAML (se queda con la última y sigue) — hay que detectarlo
    a mano, recorriendo el árbol."""
    import yaml

    class _CargadorQueNoPerdona(yaml.SafeLoader):
        pass

    def _mapa_sin_duplicados(cargador, nodo):
        vistas = {}
        for nodo_clave, nodo_valor in nodo.value:
            clave = cargador.construct_object(nodo_clave, deep=False)
            if clave in vistas:
                raise ValueError(
                    f"clave repetida {clave!r} en la línea {nodo_clave.start_mark.line + 1} "
                    f"(la primera está en la línea {vistas[clave] + 1})")
            vistas[clave] = nodo_clave.start_mark.line
            cargador.construct_object(nodo_valor, deep=False)
        return vistas

    _CargadorQueNoPerdona.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapa_sin_duplicados)

    workflows = sorted((RAIZ / ".github/workflows").glob("*.yml"))
    assert workflows, "no se encontraron workflows para chequear"
    for archivo in workflows:
        try:
            with archivo.open(encoding="utf-8") as f:
                yaml.load(f, Loader=_CargadorQueNoPerdona)
        except ValueError as e:
            raise AssertionError(f"{archivo.relative_to(RAIZ)}: {e}") from e


# --- la demo del programa instalado no se regala -----------------------------

def test_la_landing_no_ofrece_descargar_ningun_binario():
    """El instalador, el portable, la edición BAT y el APK estuvieron colgados
    de la landing con enlace directo: cualquiera se llevaba el producto entero
    sin dejar un nombre. Ahora el visitante prueba la app en el navegador y el
    programa instalado se muestra en una demo uno a uno.

    Se mira la salida generada, no el generador: el bug volvería agregando un
    ítem a `desc_items`, y ahí el .py sigue leyéndose igual de bien.
    """
    binarios = re.compile(r"https?://[^\"']*\.(?:exe|zip|apk|aab|msi)\b", re.I)
    paginas = [RAIZ / "landing" / "index.html",
               RAIZ / "landing" / "pt" / "index.html",
               RAIZ / "landing" / "en" / "index.html",
               RAIZ / "public" / "index.html",
               RAIZ / "public" / "pt" / "index.html",
               RAIZ / "public" / "en" / "index.html"]
    revisadas = 0
    for p in paginas:
        if not p.exists():       # public/ lo arma el build; landing/ el generador
            continue
        revisadas += 1
        hallados = sorted(set(binarios.findall(p.read_text(encoding="utf-8"))))
        assert not hallados, (
            f"{p.relative_to(RAIZ)} vuelve a enlazar binarios: {hallados}. "
            "La demo del programa instalado se da en vivo (sección #demo).")
    assert revisadas, "no se generó ninguna página: corré marketing.generar_landing"


def test_el_formulario_de_demo_pide_los_datos_que_filtran():
    """Sin nombre, empresa y país el formulario no filtra nada: deja de ser un
    registro de quién pidió acceso y pasa a ser un buzón anónimo."""
    for sufijo in ("", "pt/", "en/"):
        p = RAIZ / "landing" / sufijo / "index.html"
        if not p.exists():
            continue
        html = p.read_text(encoding="utf-8")
        assert 'id="demo-form"' in html, f"{p.relative_to(RAIZ)}: falta el formulario"
        assert "/api/demo/solicitar" in html, (
            f"{p.relative_to(RAIZ)}: el formulario no le pide la demo al backend")
        for campo in ("nombre", "empresa", "pais", "email"):
            assert re.search(rf'name="{campo}"[^>]*\brequired\b', html), (
                f"{p.relative_to(RAIZ)}: «{campo}» no es obligatorio")
