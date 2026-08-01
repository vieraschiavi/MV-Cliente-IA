"""
MV Cliente IA · pipeline AutoGTM
=================================
Orquesta las seis fases y va publicando el estado de cada una para que la
interfaz pinte el acordeón en vivo (mismo comportamiento que el auto-GTM de
Explee: los pasos se van marcando en verde a medida que terminan).

Correr desde la línea de comandos:

    python -m cliente_ia.pipeline mvkobranzaia.com --modo demo --prospectos 60

El pipeline no toca la red salvo que se le pida modo `web` o `llm`; en modo
demo es determinista y por eso es el que corre en los tests.
"""
from __future__ import annotations

import argparse
import json
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from . import almacen, geo, proveedores, redaccion, scoring
from . import enlaces as menlaces
from .modelos import FASES, Corrida, Email, Prospecto

LIMITE_PROSPECTOS_DEFAULT = 60
DECISORES_POR_EMPRESA_DEFAULT = 3
# Tope de correos por corrida: escribirle a los 500 decisores de una lista es
# lo que quema un dominio. Se redacta para los mejores y el resto queda en la
# tabla, listo para la siguiente tanda.
LIMITE_EMAILS_DEFAULT = 40

Progreso = Callable[[Corrida], None]


def _ahora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class _Reloj:
    def __init__(self):
        self.t0 = time.perf_counter()

    def ms(self) -> int:
        return int((time.perf_counter() - self.t0) * 1000)


def ejecutar(dominio: str,
             modo: str = "demo",
             limite_prospectos: int = LIMITE_PROSPECTOS_DEFAULT,
             decisores_por_empresa: int = DECISORES_POR_EMPRESA_DEFAULT,
             limite_emails: int = LIMITE_EMAILS_DEFAULT,
             idioma_ui: str = "es",
             firma: str = "",
             nombre: str = "",
             enlaces: dict | menlaces.Enlaces | None = None,
             al_avanzar: Progreso | None = None,
             corrida_id: str = "",
             clave_ia: str = "") -> Corrida:
    """
    Corre el AutoGTM completo sobre `dominio` y devuelve la corrida.

    `al_avanzar` se llama después de cada fase con la corrida entera — es lo
    que usa el backend para persistir el avance y que el frontend lo lea sin
    esperar a que termine todo.

    `enlaces` configura el sitio, el video y el banner que llevan los mensajes
    de la fase 6, cada uno en el idioma del receptor (ver `cliente_ia.enlaces`).
    Si no se pasa nada, se derivan del dominio del producto.
    """
    dominio = (dominio or "").strip().lower().removeprefix("https://") \
                                            .removeprefix("http://").rstrip("/")
    if not dominio:
        raise ValueError("Hace falta un dominio")

    corrida = Corrida(
        id=corrida_id or uuid.uuid4().hex[:12],
        dominio=dominio,
        creada=_ahora(),
        estado="corriendo",
        modo=proveedores.modo_efectivo(modo, clave_ia),
        idioma_ui=idioma_ui if idioma_ui in geo.IDIOMAS else "es",
        pasos=[],
    )
    cfg_enlaces = (enlaces if isinstance(enlaces, menlaces.Enlaces)
                   else menlaces.desde_dict(enlaces, dominio))
    corrida.enlaces = cfg_enlaces.a_dict()
    for clave in FASES:
        corrida.paso(clave)

    def avisar():
        if al_avanzar:
            al_avanzar(corrida)

    avisar()
    # La clave de la interfaz vive lo que dura esta llamada: no entra en la
    # corrida, ni en el disco, ni en ningún log.
    proveedor = proveedores.construir(modo, corrida.idioma_ui, clave_ia)

    try:
        # --- Fase 1 · investigar la empresa -----------------------------
        with _fase(corrida, "investigar", avisar) as paso:
            corrida.empresa = proveedor.investigar(dominio)
            # Un dominio pegado no siempre tiene un nombre comercial legible
            # ("mvkobranzaia.com" → "Mvkobranzaia"). Si el usuario lo escribió,
            # manda el suyo: es el nombre que van a leer los destinatarios.
            if nombre.strip():
                corrida.empresa.nombre = nombre.strip()
                corrida.empresa.propuesta = _con_nombre(corrida.empresa, corrida.idioma_ui)
            paso.items = 1
            paso.detalle = corrida.empresa.categoria

        # --- Fase 2 · explorar la competencia ---------------------------
        with _fase(corrida, "competencia", avisar) as paso:
            corrida.competidores = proveedor.competencia(corrida.empresa)
            paso.items = len(corrida.competidores)
            paso.detalle = ", ".join(c.dominio for c in corrida.competidores[:3])

        # --- Fase 3 · definir campañas ----------------------------------
        with _fase(corrida, "campanas", avisar) as paso:
            corrida.campanas = proveedor.campanas(corrida.empresa, corrida.competidores)
            paso.items = len(corrida.campanas)
            paso.detalle = _detalle_olas(corrida)

        # --- Fase 4 · encontrar clientes potenciales --------------------
        with _fase(corrida, "prospectos", avisar) as paso:
            crudos = proveedor.prospectos(corrida.empresa, corrida.campanas, limite_prospectos)
            nombres_comp = [c.nombre for c in corrida.competidores]
            for p in crudos:
                scoring.puntuar_prospecto(p, corrida.empresa, nombres_comp)
            # Uruguay primero, después LATAM, después el mundo. El recorte al
            # límite se hace DESPUÉS de ordenar: si sobran candidatos, los que
            # se caen son siempre los del final de la cola, nunca los locales.
            corrida.prospectos = scoring.ordenar_prospectos(crudos)[:limite_prospectos]
            paso.items = len(corrida.prospectos)
            paso.detalle = _detalle_niveles(corrida.prospectos)

        # --- Fase 5 · encontrar decisores -------------------------------
        with _fase(corrida, "decisores", avisar) as paso:
            decisores = proveedor.decisores(corrida.prospectos, decisores_por_empresa)
            por_id = {p.id: p for p in corrida.prospectos}
            for d in decisores:
                prospecto = por_id.get(d.prospecto_id)
                if prospecto:
                    scoring.puntuar_decisor(d, prospecto)
            corrida.decisores = scoring.ordenar_decisores(
                [d for d in decisores if d.prospecto_id in por_id])
            paso.items = len(corrida.decisores)
            paso.detalle = _detalle_niveles(corrida.prospectos)

        # --- Fase 6 · escribir los correos ------------------------------
        with _fase(corrida, "emails", avisar) as paso:
            corrida.emails = _redactar_todos(corrida, limite_emails, firma, cfg_enlaces)
            paso.items = len(corrida.emails)
            paso.detalle = _detalle_idiomas(corrida.emails)

        corrida.estado = "listo"
    except Exception as e:                                  # noqa: BLE001
        corrida.estado = "error"
        corrida.error = f"{type(e).__name__}: {e}"
        for p in corrida.pasos:
            if p.estado == "corriendo":
                p.estado = "error"
                p.detalle = corrida.error
    # Lo que la cadena de proveedores absorbió sin tumbar la corrida (p. ej.
    # el LLM falló y lo cubrió el demo) se muestra, no se esconde.
    corrida.avisos = list(getattr(proveedor, "errores", []))
    avisar()
    return corrida


def _con_nombre(empresa, idioma: str) -> str:
    """Rearma la propuesta de la interfaz con el nombre comercial elegido."""
    cuerpo = (empresa.textos.get(idioma) or {}).get("propuesta", "")
    return f"{empresa.nombre} {cuerpo}." if cuerpo else empresa.propuesta


class _fase:
    """Marca la fase como corriendo, mide el tiempo y la cierra en 'listo'."""

    def __init__(self, corrida: Corrida, clave: str, avisar: Callable[[], None]):
        self.corrida, self.clave, self.avisar = corrida, clave, avisar

    def __enter__(self):
        self.reloj = _Reloj()
        self.paso = self.corrida.paso(self.clave)
        self.paso.estado = "corriendo"
        self.avisar()
        return self.paso

    def __exit__(self, exc_tipo, exc, tb):
        self.paso.ms = self.reloj.ms()
        if exc_tipo is None:
            self.paso.estado = "listo"
            self.avisar()
        return False


# Cómo se reparte la tanda de correos entre las tres olas. Uruguay se lleva
# la mayor parte, pero las tres arrancan a la vez: si la tanda fuera
# estrictamente por prioridad, LATAM y el resto del mundo no recibirían un
# solo correo hasta agotar Uruguay — y con eso el producto no probaría nunca
# los otros dos idiomas en la calle.
REPARTO_EMAILS = {"local": 0.45, "latam": 0.35, "mundo": 0.20}


def _redactar_todos(corrida: Corrida, limite: int, firma: str,
                    cfg_enlaces: menlaces.Enlaces) -> list[Email]:
    por_id = {p.id: p for p in corrida.prospectos}
    campanas = {c.id: c for c in corrida.campanas}
    emails: list[Email] = []

    for nivel in ("local", "latam", "mundo"):
        decisores = [d for d in corrida.decisores
                     if (p := por_id.get(d.prospecto_id)) and p.nivel == nivel]
        if not decisores:
            continue
        cupo = max(1, round(limite * REPARTO_EMAILS[nivel]))
        # Un correo por empresa antes del segundo de la misma empresa:
        # escribirle a tres personas de la misma casa el mismo día quema el
        # dominio. Recién cuando toda la ola tiene su primer contacto se
        # empieza la segunda vuelta.
        escritos: set[str] = set()
        for vuelta in (1, 2, 3):
            for d in decisores:
                if len(emails) >= limite or cupo <= 0:
                    break
                clave = f"{d.prospecto_id}:{vuelta}"
                if clave in escritos or (vuelta > 1
                                         and f"{d.prospecto_id}:{vuelta - 1}" not in escritos):
                    continue
                if any(e.decisor_id == d.id for e in emails):
                    continue
                escritos.add(clave)
                cupo -= 1
                prospecto = por_id[d.prospecto_id]
                emails.append(redaccion.redactar(
                    d, prospecto, corrida.empresa,
                    campanas.get(prospecto.campana_id), firma, cfg_enlaces))
    return emails


def _detalle_olas(corrida: Corrida) -> str:
    conteo: dict[str, int] = {}
    for c in corrida.campanas:
        conteo[c.nivel] = conteo.get(c.nivel, 0) + 1
    return " · ".join(f"{k}: {v}" for k, v in conteo.items())


def _detalle_niveles(prospectos: list[Prospecto]) -> str:
    conteo = {"local": 0, "latam": 0, "mundo": 0}
    for p in prospectos:
        conteo[p.nivel] = conteo.get(p.nivel, 0) + 1
    return f"UY {conteo['local']} · LATAM {conteo['latam']} · Mundo {conteo['mundo']}"


def _detalle_idiomas(emails: list[Email]) -> str:
    conteo: dict[str, int] = {}
    for e in emails:
        conteo[e.idioma] = conteo.get(e.idioma, 0) + 1
    return " · ".join(f"{k}: {v}" for k, v in sorted(conteo.items()))


def _cli() -> int:
    ap = argparse.ArgumentParser(description="MV Cliente IA · AutoGTM end-to-end")
    ap.add_argument("dominio", help="Dominio del producto a vender, ej. mvkobranzaia.com")
    ap.add_argument("--modo", default="demo", choices=list(proveedores.MODOS))
    ap.add_argument("--prospectos", type=int, default=LIMITE_PROSPECTOS_DEFAULT)
    ap.add_argument("--decisores", type=int, default=DECISORES_POR_EMPRESA_DEFAULT)
    ap.add_argument("--emails", type=int, default=LIMITE_EMAILS_DEFAULT)
    ap.add_argument("--idioma", default="es", choices=list(geo.IDIOMAS))
    ap.add_argument("--firma", default="")
    ap.add_argument("--nombre", default="", help="Nombre comercial, ej. 'MV Kobra AI'")
    ap.add_argument("--sitio", default="", help="Sitio para los enlaces (por defecto, el dominio)")
    ap.add_argument("--video-es", default="", help="URL del video en español")
    ap.add_argument("--video-pt", default="", help="URL del video en portugués")
    ap.add_argument("--video-en", default="", help="URL del video en inglés")
    ap.add_argument("--video-en-landing", action="store_true",
                    help="Sin videos propios, enlazar la sección de video de la landing")
    ap.add_argument("--json", action="store_true", help="Volcar la corrida entera a stdout")
    args = ap.parse_args()

    def mostrar(c: Corrida):
        for p in c.pasos:
            if p.estado == "listo" and not getattr(p, "_dicho", False):
                p._dicho = True                            # noqa: SLF001
                print(f"  ✓ {p.clave:<12} {p.items:>4} · {p.detalle} ({p.ms} ms)")

    print(f"▸ AutoGTM sobre {args.dominio} (modo {args.modo})")
    corrida = ejecutar(args.dominio, modo=args.modo,
                       limite_prospectos=args.prospectos,
                       decisores_por_empresa=args.decisores,
                       limite_emails=args.emails,
                       idioma_ui=args.idioma, firma=args.firma, nombre=args.nombre,
                       enlaces={"sitio": args.sitio or args.dominio,
                                "videos": {"es": args.video_es, "pt": args.video_pt,
                                           "en": args.video_en},
                                "video_en_landing": args.video_en_landing},
                       al_avanzar=mostrar)
    almacen.guardar(corrida)
    if args.json:
        print(json.dumps(corrida.a_dict(), ensure_ascii=False, indent=2))
    else:
        r = corrida.resumen()
        print(f"\n  estado: {corrida.estado}")
        print(f"  prospectos por ola: {r['prospectos_por_nivel']}")
        print(f"  correos por idioma: {r['emails_por_idioma']}")
        print(f"  con video: {r['con_video']} · con LinkedIn: {r['con_linkedin']}")
        print(f"  guardada en: {almacen.ruta_de(corrida.id)}")
    return 0 if corrida.estado == "listo" else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
