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
             clave_ia: str = "",
             proveedor_ia: str = "claude",
             endpoint_ia: str = "",
             modelo_ia: str = "",
             mercado: str = "todos",
             pais_base: str = "") -> Corrida:
    """
    Corre el AutoGTM completo sobre `dominio` y devuelve la corrida.

    `al_avanzar` se llama después de cada fase con la corrida entera — es lo
    que usa el backend para persistir el avance y que el frontend lo lea sin
    esperar a que termine todo.

    `enlaces` configura el sitio, el video y el banner que llevan los mensajes
    de la fase 6, cada uno en el idioma del receptor (ver `cliente_ia.enlaces`).
    Si no se pasa nada, se derivan del dominio del producto.

    `pais_base` es el mercado propio del cliente: el que va primero en las tres
    olas. Vacío significa «deducilo» (del TLD del dominio, y si es genérico del
    idioma de la interfaz).
    """
    dominio = (dominio or "").strip().lower().removeprefix("https://") \
                                            .removeprefix("http://").rstrip("/")
    if not dominio:
        raise ValueError("Hace falta un dominio")
    # "latam" es como se llamaba la ola regional antes de que el país base
    # fuera elegible; un navegador con el filtro viejo guardado lo sigue
    # mandando.
    if mercado == "latam":
        mercado = geo.NIVEL_REGIONAL
    if mercado not in ("todos", *geo.NIVELES):
        raise ValueError(f"Mercado inválido: {mercado}")

    base = geo.resolver_base(pais_base, dominio, idioma_ui)

    corrida = Corrida(
        id=corrida_id or uuid.uuid4().hex[:12],
        dominio=dominio,
        creada=_ahora(),
        estado="corriendo",
        modo=proveedores.modo_efectivo(modo, clave_ia),
        mercado=mercado,
        pais_base=base.codigo,
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
    proveedor = proveedores.construir(modo, corrida.idioma_ui, clave_ia,
                                      proveedor_ia, endpoint_ia, mercado,
                                      base.codigo, modelo_ia)

    try:
        # --- Fase 1 · investigar la empresa -----------------------------
        with _fase(corrida, "investigar", avisar) as paso:
            corrida.empresa = proveedor.investigar(dominio)
            # El mercado base del cliente manda sobre lo que dedujo la fase 1:
            # el TLD es una pista, la elección del usuario es un dato. Todo el
            # resto del pipeline lee las olas desde acá.
            corrida.empresa.pais = base.codigo
            # Un dominio pegado no siempre tiene un nombre comercial legible
            # ("mvkobranzaia.com" → "Mvkobranzaia"). Si el usuario lo escribió,
            # manda el suyo: es el nombre que van a leer los destinatarios.
            if nombre.strip():
                corrida.empresa.nombre = nombre.strip()
                corrida.empresa.propuesta = _con_nombre(corrida.empresa, corrida.idioma_ui)
            # Con IA, el NICHO se deduce del sitio real. Sin esto, categoría,
            # sectores, dolores y diferenciales salían del catálogo demo (de
            # cobranzas) y eran los mismos para cualquier producto.
            if modo != "demo" and not corrida.empresa.resumen_sitio:
                # No hay producto que leer en esa dirección: perfilar acá
                # sería inventar. Un usuario pegó la URL de su panel de
                # Vercel y le salió un perfil de cobranzas completo, con
                # competidores de cobranzas y todo.
                corrida.avisos.append(
                    "En esa dirección no hay una descripción de tu producto: "
                    "parece un panel de administración o una página que se "
                    "dibuja por JavaScript. Pegá la URL pública que ven tus "
                    "clientes. Mientras tanto el perfil es el del catálogo "
                    "genérico y no describe tu producto.")
            else:
                try:
                    corrida.empresa = proveedor.perfilar(corrida.empresa)
                except NotImplementedError:
                    # Sin IA no hay quién deduzca el nicho: se usa el del
                    # catálogo, pero se dice — si no, los mismos cinco sectores
                    # aparecen para cualquier producto y parecen investigados.
                    if modo != "demo":
                        corrida.avisos.append(
                            "El nicho y los sectores objetivo son los del catálogo "
                            "genérico: para deducirlos de tu web hace falta el modo "
                            "«Investigación con IA» con tu clave.")
                except Exception:                        # noqa: BLE001
                    # Con IA, el motivo del fallo ya quedó en los errores de la
                    # cadena, que el final de la corrida copia a los avisos. Se
                    # sigue con el perfil del catálogo: es peor no tener fase 1.
                    pass
            paso.items = 1
            paso.detalle = corrida.empresa.categoria

        # --- Fase 2 · explorar la competencia ---------------------------
        with _fase(corrida, "competencia", avisar) as paso:
            corrida.competidores = proveedor.competencia(corrida.empresa)
            # El mismo recorte de mercado que campañas y prospectos, que acá
            # faltaba: con «sólo Uruguay» elegido aparecían competidores de
            # Brasil y EE.UU. como si nada. Si el recorte no deja ninguno se
            # muestran todos CON aviso — seis de afuera diciéndolo es más
            # útil que una fase en cero sin explicación.
            if mercado != "todos" and corrida.competidores:
                dentro = [c for c in corrida.competidores if c.pais and
                          geo.nivel_de(c.pais, corrida.pais_base) == mercado]
                if dentro:
                    corrida.competidores = dentro
                else:
                    corrida.avisos.append(
                        "Ningún competidor conocido tiene base en el mercado "
                        f"elegido ({_nombre_mercado(mercado, corrida)}); se "
                        "muestran los de todos lados.")
            paso.items = len(corrida.competidores)
            paso.detalle = ", ".join(c.dominio for c in corrida.competidores[:3])

        # --- Fase 3 · definir campañas ----------------------------------
        with _fase(corrida, "campanas", avisar) as paso:
            corrida.campanas = proveedor.campanas(corrida.empresa, corrida.competidores)
            # Filtro de mercado: con «sólo mi país» (o mi región, o mundo) las
            # campañas de las otras olas se descartan acá, ANTES de buscar
            # prospectos — los proveedores derivan las olas de las campañas
            # que reciben y renormalizan el reparto sobre las presentes.
            if mercado != "todos":
                filtradas = [c for c in corrida.campanas if c.nivel == mercado]
                if filtradas:
                    corrida.campanas = filtradas
                else:
                    corrida.avisos.append(
                        f"El recorte de mercado «{mercado}» no dejó campañas; "
                        "se usaron todas las olas.")
            paso.items = len(corrida.campanas)
            paso.detalle = _detalle_olas(corrida)

        # --- Fase 4 · encontrar clientes potenciales --------------------
        with _fase(corrida, "prospectos", avisar) as paso:
            crudos = proveedor.prospectos(corrida.empresa, corrida.campanas, limite_prospectos)
            nombres_comp = [c.nombre for c in corrida.competidores]
            for p in crudos:
                scoring.puntuar_prospecto(p, corrida.empresa, nombres_comp)
            # El país del cliente primero, después su región, después el mundo.
            # El recorte al límite se hace DESPUÉS de ordenar: si sobran
            # candidatos, los que se caen son siempre los del final de la cola,
            # nunca los del mercado propio.
            corrida.prospectos = scoring.ordenar_prospectos(crudos)[:limite_prospectos]
            paso.items = len(corrida.prospectos)
            paso.detalle = _detalle_niveles(corrida.prospectos, base.codigo, corrida.idioma_ui)

        # --- Fase 5 · encontrar decisores -------------------------------
        with _fase(corrida, "decisores", avisar) as paso:
            # Antes de los cargos, los contactos PÚBLICOS de cada empresa
            # real: su sitio dice cómo quiere que la contacten (info@,
            # teléfono, LinkedIn, Instagram). Nada se inventa.
            from .proveedores import contactos as mod_contactos
            con_datos, visitados = mod_contactos.enriquecer(corrida.prospectos)
            if visitados:
                corrida.avisos.append(
                    f"Contactos públicos: {con_datos} de {visitados} empresas "
                    "reales publican correo, teléfono o redes en su sitio.")
            decisores = proveedor.decisores(corrida.prospectos, decisores_por_empresa)
            por_id = {p.id: p for p in corrida.prospectos}
            for d in decisores:
                prospecto = por_id.get(d.prospecto_id)
                if prospecto:
                    scoring.puntuar_decisor(d, prospecto)
            corrida.decisores = scoring.ordenar_decisores(
                [d for d in decisores if d.prospecto_id in por_id], base.codigo)
            paso.items = len(corrida.decisores)
            paso.detalle = _detalle_niveles(corrida.prospectos, base.codigo, corrida.idioma_ui)

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
    # el LLM falló y lo cubrió el demo) se muestra, no se esconde. Se suma a
    # los avisos que el propio pipeline haya dejado (p. ej. el del filtro de
    # mercado) en vez de pisarlos.
    corrida.avisos.extend(getattr(proveedor, "errores", []))
    for p in getattr(proveedor, "proveedores", []):
        corrida.avisos.extend(getattr(p, "notas", []))
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
REPARTO_EMAILS = {geo.NIVEL_LOCAL: 0.45, geo.NIVEL_REGIONAL: 0.35,
                  geo.NIVEL_MUNDO: 0.20}


def _redactar_todos(corrida: Corrida, limite: int, firma: str,
                    cfg_enlaces: menlaces.Enlaces) -> list[Email]:
    por_id = {p.id: p for p in corrida.prospectos}
    campanas = {c.id: c for c in corrida.campanas}
    emails: list[Email] = []

    for nivel in geo.NIVELES:
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


def _nombre_mercado(mercado: str, corrida: Corrida) -> str:
    """El recorte elegido, con nombre y apellido para el aviso: «Uruguay»
    dice más que «local»."""
    if mercado == geo.NIVEL_LOCAL:
        return geo.nombre_pais(corrida.pais_base, corrida.idioma_ui)
    if mercado == geo.NIVEL_REGIONAL:
        return geo.nombre_region(geo.region_de(corrida.pais_base),
                                 corrida.idioma_ui)
    return "resto del mundo"


def _detalle_olas(corrida: Corrida) -> str:
    conteo: dict[str, int] = {}
    for c in corrida.campanas:
        conteo[c.nivel] = conteo.get(c.nivel, 0) + 1
    return " · ".join(f"{k}: {v}" for k, v in conteo.items())


def _detalle_niveles(prospectos: list[Prospecto], base: str = "",
                     idioma: str = "es") -> str:
    conteo = dict.fromkeys(geo.NIVELES, 0)
    for p in prospectos:
        conteo[geo.normalizar_nivel(p.nivel)] += 1
    pais = geo.obtener(base)
    region = geo.nombre_region(pais.region, idioma)
    return (f"{geo.nombre_pais(base, idioma)} {conteo[geo.NIVEL_LOCAL]} · "
            f"{region} {conteo[geo.NIVEL_REGIONAL]} · "
            f"Mundo {conteo[geo.NIVEL_MUNDO]}")


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
    ap.add_argument("--pais", default="",
                    help="Tu mercado, ISO alfa-2 (UY, DE, JP…). Vacío: se deduce "
                         "del TLD del dominio y, si es genérico, del idioma")
    ap.add_argument("--mercado", default="todos",
                    choices=["todos", *geo.NIVELES],
                    help="Recorte: todos | local (tu país) | regional (tu región) | mundo")
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
                       pais_base=args.pais, mercado=args.mercado,
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
        print(f"  mercado base: {geo.nombre_pais(corrida.pais_base, args.idioma)}")
        print(f"  prospectos por ola: {r['prospectos_por_nivel']}")
        print(f"  correos por idioma: {r['emails_por_idioma']}")
        print(f"  con video: {r['con_video']} · con LinkedIn: {r['con_linkedin']}")
        print(f"  guardada en: {almacen.ruta_de(corrida.id)}")
    return 0 if corrida.estado == "listo" else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
