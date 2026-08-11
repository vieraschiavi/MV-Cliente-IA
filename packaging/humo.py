"""
MV Cliente IA · prueba de humo contra un motor vivo
====================================================
Le pega por HTTP a un programa que ya está corriendo y comprueba que hace lo
que promete: las seis fases, las olas geográficas en orden, los correos en el
idioma del decisor, el dato sintético marcado y las exportaciones.

Existe porque el resto de la suite usa `TestClient`, que llama a la aplicación
en el mismo proceso. Eso NO prueba lo que el cliente ejecuta: un `.exe` que
arranca, un `.bat` que armó su entorno, uvicorn escuchando en un puerto. Esto
se corre igual en Linux y en Windows, contra la edición BAT y contra la EXE,
y es lo que decide si una versión se publica o no.

    python packaging/humo.py --url http://127.0.0.1:8810
    python packaging/humo.py --url http://127.0.0.1:8810 --edicion demo
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from io import BytesIO

ESPERA_CORRIDA = 300.0


class Fallo(Exception):
    """Una comprobación que no pasó. El mensaje va tal cual a la salida."""


def _pedir(url: str, metodo: str = "GET", cuerpo: dict | None = None,
           timeout: float = 60.0) -> tuple[int, bytes, str]:
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo)
    if datos is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "")


def _json(url: str, metodo: str = "GET", cuerpo: dict | None = None,
          timeout: float = 60.0) -> dict:
    codigo, crudo, _ = _pedir(url, metodo, cuerpo, timeout)
    if codigo != 200:
        raise Fallo(f"{metodo} {url} devolvió {codigo}: {crudo[:300].decode(errors='replace')}")
    return json.loads(crudo)


def esperar_motor(base: str, espera: float) -> bool:
    """Le da tiempo a arrancar antes de la primera comprobación.

    Hace falta de verdad: la edición BAT, la primera vez, instala sus
    dependencias antes de levantar el motor. Sin esta espera la prueba
    llegaría temprano y diría que el programa no anda cuando en realidad
    todavía se estaba preparando.
    """
    limite = time.monotonic() + espera
    while True:
        try:
            with urllib.request.urlopen(f"{base}/api/salud", timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError, ValueError):
            pass
        if time.monotonic() >= limite:
            return False
        time.sleep(1.0)


def comprobar_salud(base: str) -> dict:
    d = _json(f"{base}/api/salud")
    if not d.get("ok"):
        raise Fallo(f"/api/salud no dice ok: {d}")
    if d.get("sin_estado"):
        raise Fallo("el motor arrancó en modo sin estado (serverless); "
                    "el programa instalado tiene que guardar las corridas")
    return d


def comprobar_interfaz(base: str) -> None:
    """La React tiene que estar servida de verdad, no sólo la API. Si falta el
    build, el usuario ve un 404 en blanco y cree que el programa está roto."""
    codigo, cuerpo, tipo = _pedir(f"{base}/")
    if codigo != 200:
        raise Fallo(f"la portada devolvió {codigo}; falta el build de React")
    if "text/html" not in tipo:
        raise Fallo(f"la portada no es HTML sino {tipo!r}")
    texto = cuerpo.decode(errors="replace")
    if "<div id=\"root\"" not in texto and "<div id=root" not in texto:
        raise Fallo("la portada no tiene el punto de montaje de React")
    # El HTML referencia el bundle con hash; que exista prueba que los
    # estáticos se están sirviendo y no sólo el index. Vite los escribe
    # relativos (`./assets/...`) para que la misma build sirva en la web, en
    # Electron (file://) y en el APK — por eso no se busca sólo `/assets`.
    import re
    m = re.search(r'(?:src|href)="\.?(/assets/[^"]+\.(?:js|css))"', texto)
    if not m:
        raise Fallo("la portada no referencia ningún bundle de assets")
    codigo, _, _ = _pedir(f"{base}{m.group(1)}")
    if codigo != 200:
        raise Fallo(f"el bundle {m.group(1)} devolvió {codigo}")


def comprobar_licencia(base: str, esperada: str = "") -> dict:
    d = _json(f"{base}/api/licencia")
    if esperada and d.get("edicion") != esperada:
        raise Fallo(f"la edición es {d.get('edicion')!r} y se esperaba {esperada!r}")
    if esperada == "demo" and not d.get("activa"):
        raise Fallo(f"la edición demo tendría que abrir sin clave: {d}")
    if esperada == "cliente" and d.get("activa"):
        raise Fallo("la edición cliente abrió sin clave de licencia")
    return d


def comprobar_geo(base: str) -> None:
    """La regla que no se rompe: el país elegido primero, después su región,
    después el resto. Y que sea RELATIVO — con otro país base se da vuelta."""
    for pais, region_propia in (("UY", "AR"), ("JP", "KR"), ("DE", "FR")):
        d = _json(f"{base}/api/geo?pais={pais}")
        olas = d.get("olas") or []
        if len(olas) != 3:
            raise Fallo(f"/api/geo?pais={pais} devolvió {len(olas)} olas, no 3")
        niveles = [o.get("nivel") for o in olas]
        if niveles != ["local", "regional", "mundo"]:
            raise Fallo(f"olas fuera de orden para {pais}: {niveles}")
        locales = [p["codigo"] for p in (olas[0].get("paises") or [])]
        if locales != [pais]:
            raise Fallo(f"la ola local de {pais} es {locales}, tendría que ser ['{pais}']")
        regionales = [p["codigo"] for p in (olas[1].get("paises") or [])]
        if region_propia not in regionales:
            raise Fallo(f"{region_propia} no está en la ola regional de {pais}")
        if pais in regionales:
            raise Fallo(f"{pais} aparece en su propia ola regional además de la local")
        if d.get("pais_base") != pais:
            raise Fallo(f"pais_base es {d.get('pais_base')!r} y se pidió {pais!r}")


def lanzar_corrida(base: str, dominio: str, prospectos: int, idioma: str) -> dict:
    inicio = _json(f"{base}/api/corridas", "POST", {
        "dominio": dominio, "modo": "demo", "mercado": "todos",
        "pais": "UY", "idioma": idioma, "prospectos": prospectos,
    })
    cid = inicio.get("id")
    if not cid:
        raise Fallo(f"la corrida no devolvió id: {inicio}")
    limite = time.monotonic() + ESPERA_CORRIDA
    ultimo: dict = {}
    while time.monotonic() < limite:
        ultimo = _json(f"{base}/api/corridas/{cid}")
        if ultimo.get("estado") == "listo":
            return ultimo
        if ultimo.get("estado") == "error":
            raise Fallo(f"la corrida falló: {ultimo.get('error')}")
        time.sleep(1.0)
    raise Fallo(f"la corrida no terminó en {ESPERA_CORRIDA:.0f}s "
                f"(quedó en {ultimo.get('estado')!r})")


def comprobar_corrida(c: dict, prospectos: int) -> None:
    pasos = c.get("pasos") or []
    if len(pasos) != 6:
        raise Fallo(f"la corrida tiene {len(pasos)} fases, no 6")
    fallidas = [p.get("clave") for p in pasos if p.get("estado") != "listo"]
    if fallidas:
        raise Fallo(f"fases que no terminaron: {fallidas}")
    if not c.get("empresa"):
        raise Fallo("la corrida no trajo la empresa investigada (fase 1)")
    for clave in ("competidores", "campanas", "prospectos", "decisores", "emails"):
        if not c.get(clave):
            raise Fallo(f"la corrida no trajo nada en {clave}")

    hallados = len(c["prospectos"])
    if hallados > prospectos:
        raise Fallo(f"se pidieron {prospectos} prospectos y volvieron {hallados}")

    # El país del cliente primero: ningún prospecto de una ola posterior puede
    # colarse delante de uno de la ola propia.
    orden = {"local": 1, "regional": 2, "latam": 2, "mundo": 3}
    vistos = [orden.get(p.get("nivel", ""), 9) for p in c["prospectos"]]
    if vistos != sorted(vistos):
        raise Fallo(f"los prospectos no están ordenados por ola: {vistos[:12]}")

    # Datos sintéticos marcados como tales, sin excepción.
    sin_marcar = [d.get("nombre") for d in c["decisores"] if not d.get("sintetico")]
    if sin_marcar:
        raise Fallo(f"decisores sintéticos sin marcar: {sin_marcar[:3]}")

    # El idioma del correo lo decide el país del DECISOR, no la interfaz: la
    # corrida se lanzó con idioma_ui="es" y aun así tiene que haber correos en
    # pt y en en para los decisores de esos países.
    decisores = {d["id"]: d for d in c["decisores"]}
    idiomas = {e.get("idioma") for e in c["emails"]}
    if not idiomas <= {"es", "pt", "en"}:
        raise Fallo(f"correos en idiomas inesperados: {idiomas}")
    if c.get("idioma_ui") == "es" and idiomas == {"es"} and len(decisores) > 10:
        raise Fallo("todos los correos salieron en español: el idioma lo está "
                    "decidiendo la interfaz y no el país del decisor")
    for e in c["emails"]:
        if not (e.get("asunto") or "").strip():
            raise Fallo("hay un correo sin asunto")
        cuerpo = (e.get("cuerpo") or "").strip()
        if not cuerpo:
            raise Fallo("hay un correo sin cuerpo")
        d = decisores.get(e.get("decisor_id"))
        if d and d.get("idioma") != e.get("idioma"):
            raise Fallo(f"el correo a {d.get('nombre')} ({d.get('pais')}, "
                        f"idioma {d.get('idioma')}) salió en {e.get('idioma')}")
        # Regresión ya arreglada una vez: los correos en PT/EN llevaban un
        # párrafo en español. La apertura de interrogación y exclamación no
        # existen fuera del español, así que delatan la mezcla.
        if e.get("idioma") != "es":
            texto_todo = " ".join(filter(None, [
                e.get("asunto", ""), cuerpo, e.get("seguimiento", ""),
                e.get("linkedin", ""), e.get("linkedin_nota", ""),
            ]))
            intrusos = [s for s in ("¿", "¡") if s in texto_todo]
            if intrusos:
                raise Fallo(f"un mensaje en {e.get('idioma')} tiene puntuación "
                            f"española {intrusos}: {texto_todo[:160]!r}")


def comprobar_exportes(base: str, cid: str) -> None:
    codigo, csv, _ = _pedir(f"{base}/api/corridas/{cid}/csv")
    if codigo != 200:
        raise Fallo(f"el CSV devolvió {codigo}")
    texto = csv.decode("utf-8-sig", errors="replace")
    cabecera = texto.splitlines()[0] if texto.splitlines() else ""
    if "sintetico" not in cabecera:
        raise Fallo(f"el CSV no lleva la columna sintetico: {cabecera[:200]}")

    codigo, xlsx, _ = _pedir(f"{base}/api/corridas/{cid}/xlsx")
    if codigo != 200:
        raise Fallo(f"el XLSX devolvió {codigo}")
    try:
        with zipfile.ZipFile(BytesIO(xlsx)) as z:
            if not any(n.startswith("xl/") for n in z.namelist()):
                raise Fallo("el XLSX no parece un libro de Excel")
    except zipfile.BadZipFile as e:
        raise Fallo(f"el XLSX salió corrupto: {e}") from e


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Prueba de humo de MV Cliente IA")
    ap.add_argument("--url", default="http://127.0.0.1:8810")
    ap.add_argument("--edicion", default="", help="demo | cliente | owner")
    ap.add_argument("--dominio", default="mvkobranzaia.com")
    ap.add_argument("--prospectos", type=int, default=50)
    ap.add_argument("--esperar", type=float, default=120.0,
                    help="segundos de gracia para que el motor arranque")
    args = ap.parse_args(argv)
    base = args.url.rstrip("/")

    if not esperar_motor(base, args.esperar):
        print(f"  FALLA {base} no contestó en {args.esperar:.0f}s", file=sys.stderr)
        return 1

    pasos: list[tuple[str, object]] = []
    try:
        salud = comprobar_salud(base)
        pasos.append(("motor vivo", f"v{salud.get('version')}"))

        comprobar_interfaz(base)
        pasos.append(("interfaz React servida", "portada + bundle"))

        lic = comprobar_licencia(base, args.edicion)
        pasos.append(("licencia", f"{lic.get('edicion')} · activa={lic.get('activa')}"))

        comprobar_geo(base)
        pasos.append(("olas geográficas", "UY · JP · DE, relativas y en orden"))

        corrida = lanzar_corrida(base, args.dominio, args.prospectos, "es")
        comprobar_corrida(corrida, args.prospectos)
        r = corrida.get("resumen") or {}
        pasos.append(("corrida demo",
                      f"{len(corrida['prospectos'])} prospectos "
                      f"{r.get('prospectos_por_nivel', {})} · "
                      f"{len(corrida['emails'])} correos "
                      f"{r.get('emails_por_idioma', {})}"))

        comprobar_exportes(base, corrida["id"])
        pasos.append(("exportes", "CSV con columna sintetico · XLSX válido"))
    except Fallo as e:
        for nombre, detalle in pasos:
            print(f"  OK    {nombre}: {detalle}")
        print(f"  FALLA {e}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError) as e:
        print(f"  FALLA no se pudo hablar con {base}: {e}", file=sys.stderr)
        return 1

    for nombre, detalle in pasos:
        print(f"  OK    {nombre}: {detalle}")
    print("\nLa prueba de humo pasó entera.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
