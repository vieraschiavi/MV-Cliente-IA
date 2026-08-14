"""
MV Cliente IA · métricas de envíos y conversión (backend)
==========================================================
Lo que Explee no te da y el usuario pidió: saber, **del lado del servidor**,
qué está funcionando. No cuántos correos mandaste —eso lo sabe cualquiera—
sino a QUÉ segmento, en qué DÍA y a qué HORA le fue mejor, y qué proporción
de esos envíos terminó en una visita a la web.

Dos tipos de evento, en un JSONL que se agrega (nunca se reescribe):

- **envio**    — un mensaje que salió: programa (dominio del producto), canal
  (email/linkedin/x), segmento (sector del prospecto), nivel (la ola: local /
  regional / mundo), país, idioma, y el sello de tiempo.
- **conversion** — alguien hizo click en el enlace del mensaje y entró a la
  web. Llega por `/api/ir`, el redirect firmado: sólo cuenta un click cuyo
  token FIRMAMOS nosotros, así que no se puede inflar la conversión a mano.

`resumen()` cruza los dos y saca la tasa de conversión por programa, por
segmento, por día de la semana y por hora, y marca el mejor de cada uno. CPM
y CPA salen sólo si se le pasa un costo: sin plata gastada no hay "costo por
mil" que inventar.

Sobre dónde vive esto
---------------------
En el programa instalado (PC/BAT) hay disco y esto persiste de verdad — que
es donde el usuario corre sus automatizaciones. En serverless (Vercel) el
disco es efímero: el redirect y la agregación funcionan igual, pero para que
las conversiones de correos reales (que viajan días) se acumulen hace falta
un almacenamiento durable del lado público. Está documentado en el README:
es la única pieza de infra que queda del lado del usuario.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlencode

from . import rutas

ARCHIVO = "metricas.jsonl"
CANALES = ("email", "linkedin", "x")
# Un bucket (segmento, día, hora…) con menos de esto no se corona "el mejor":
# una conversión sobre un envío es 100% y no dice nada.
MINIMO_PARA_RANKEAR = 5

_lock = threading.Lock()

DIAS_ES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _ruta() -> str:
    return str(rutas.dir_datos() / ARCHIVO)


def _secreto_traqueo() -> bytes:
    """El secreto que firma los enlaces de conversión. Dedicado: NO se reusa
    el de licencias. Sin él, el traqueo no se ofrece (los enlaces salen
    planos) — es una función que se activa poniendo la variable, no un
    default silencioso."""
    return (os.getenv("MVCLIENTE_TRAQUEO_SECRETO") or "").encode()


def hay_traqueo() -> bool:
    return bool(_secreto_traqueo())


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------
def _agregar(evento: dict) -> None:
    linea = json.dumps(evento, ensure_ascii=False, sort_keys=True)
    with _lock:
        # `a` es atómico para líneas cortas en POSIX; el instalado es
        # monoproceso, así que no hay carrera real. No se reescribe el
        # archivo: un evento perdido es mejor que corromper el historial.
        with open(_ruta(), "a", encoding="utf-8") as f:
            f.write(linea + "\n")


def registrar_envios(eventos: list[dict]) -> int:
    """Guarda una tanda de envíos. Cada uno se normaliza a las claves que
    `resumen` sabe cruzar; lo que no venga queda en '' o 0, nunca revienta."""
    n = 0
    for e in eventos or []:
        canal = str(e.get("canal", "")).strip().lower()
        if canal not in CANALES:
            continue
        _agregar({
            "tipo": "envio",
            "ts": _ts(e.get("ts")),
            "programa": str(e.get("programa", "")).strip().lower(),
            "canal": canal,
            "segmento": str(e.get("segmento", "")).strip().lower(),
            "nivel": str(e.get("nivel", "")).strip().lower(),
            "pais": str(e.get("pais", "")).strip().upper()[:2],
            "idioma": str(e.get("idioma", "")).strip().lower()[:2],
            "n": max(1, int(e.get("n", 1) or 1)),
        })
        n += 1
    return n


def registrar_conversion(datos: dict) -> None:
    _agregar({
        "tipo": "conversion",
        "ts": _ts(datos.get("ts")),
        "programa": str(datos.get("programa", "")).strip().lower(),
        "canal": str(datos.get("canal", "")).strip().lower(),
        "segmento": str(datos.get("segmento", "")).strip().lower(),
        "nivel": str(datos.get("nivel", "")).strip().lower(),
        "pais": str(datos.get("pais", "")).strip().upper()[:2],
        "idioma": str(datos.get("idioma", "")).strip().lower()[:2],
    })


def _ts(valor) -> str:
    """El sello de tiempo tal cual vino si es un ISO usable; si no, ahora.
    Se acepta el de afuera para que los tests sean deterministas y para que
    un envío conserve SU hora aunque el registro llegue más tarde."""
    if valor:
        try:
            datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
            return str(valor)
        except ValueError:
            pass
    return datetime.now().astimezone().isoformat()


# ---------------------------------------------------------------------------
# Enlace de conversión firmado (lo usa `enlaces` y lo valida `/api/ir`)
# ---------------------------------------------------------------------------
def firmar_traqueo(destino: str, meta: dict) -> str:
    """Un token que envuelve la URL de la landing y de dónde viene el click.
    Firmado: `/api/ir` sólo cuenta —y sólo redirige a— lo que salió de acá."""
    cuerpo = {"u": destino, **{k: str(v) for k, v in meta.items() if v}}
    crudo = json.dumps(cuerpo, separators=(",", ":"), sort_keys=True).encode()
    datos = base64.urlsafe_b64encode(crudo).decode().rstrip("=")
    firma = _firma(datos)
    return f"{datos}.{firma}"


def verificar_traqueo(token: str) -> dict | None:
    """El contenido del token si la firma es nuestra; None si no. Sin secreto
    configurado no se valida nada — la función está apagada."""
    secreto = _secreto_traqueo()
    if not secreto or not token or token.count(".") != 1:
        return None
    datos, firma = token.split(".", 1)
    if not hmac.compare_digest(firma, _firma(datos)):
        return None
    try:
        crudo = base64.urlsafe_b64decode(datos + "=" * (-len(datos) % 4))
        cuerpo = json.loads(crudo)
    except (ValueError, TypeError):
        return None
    return cuerpo if isinstance(cuerpo, dict) and cuerpo.get("u") else None


def _firma(datos: str) -> str:
    return base64.urlsafe_b64encode(
        hmac.new(_secreto_traqueo(), datos.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")[:32]


def url_de_traqueo(base: str, destino: str, meta: dict) -> str:
    """La URL pública que va en el correo en lugar del enlace directo:
    `<base>/api/ir?t=<token firmado>`. Un click ahí queda contado y después
    rebota a la landing real."""
    token = firmar_traqueo(destino, meta)
    return f"{base.rstrip('/')}/api/ir?" + urlencode({"t": token})


# ---------------------------------------------------------------------------
# Agregación
# ---------------------------------------------------------------------------
def _leer(programa: str = "") -> list[dict]:
    ruta = _ruta()
    if not os.path.exists(ruta):
        return []
    prog = programa.strip().lower()
    eventos = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                e = json.loads(linea)
            except json.JSONDecodeError:
                continue                             # una línea rota no tumba el resto
            if prog and e.get("programa") != prog:
                continue
            eventos.append(e)
    return eventos


def _dia_hora(ts: str) -> tuple[int, int]:
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d.weekday(), d.hour
    except ValueError:
        return -1, -1


def _tasa(envios: int, conv: int) -> float:
    return round(conv / envios, 4) if envios else 0.0


def resumen(programa: str = "", costo: float | None = None) -> dict:
    """El tablero que pidió el usuario. Dos clases de métrica, y la diferencia
    importa para que los números no mientan:

    - **Tasa de conversión por SEGMENTO / CANAL / OLA / PAÍS.** Acá el envío y
      su conversión comparten la clave (viaja firmada en el enlace), así que
      dividir conversiones/envíos del mismo grupo es correcto. Es lo que dice
      "a fintech por email le va mejor que a retail por LinkedIn".

    - **Cuándo entra la gente: DÍA y HORA de la conversión.** El día en que se
      mandó un correo y el día en que el destinatario hace click NO son el
      mismo, así que una "tasa por día" cruzando ambos sería falsa. Lo honesto
      y útil es la distribución de los clicks: si la gente entra los martes a
      las 10, mandá el martes temprano. Se cuenta sobre las conversiones, no
      es una tasa contra envíos de otro día.

    CPM/CPA sólo con `costo` (gasto real de la campaña)."""
    eventos = _leer(programa)

    dims_tasa = ("programa", "segmento", "canal", "nivel", "pais")
    env: dict[str, dict] = {d: defaultdict(int) for d in dims_tasa}
    conv: dict[str, dict] = {d: defaultdict(int) for d in dims_tasa}
    conv_dia: dict[int, int] = defaultdict(int)
    conv_hora: dict[int, int] = defaultdict(int)
    tot_env = tot_conv = 0

    for e in eventos:
        claves = {d: e.get(d, "") for d in dims_tasa}
        if e.get("tipo") == "envio":
            n = int(e.get("n", 1) or 1)
            tot_env += n
            for d in dims_tasa:
                env[d][claves[d]] += n
        elif e.get("tipo") == "conversion":
            tot_conv += 1
            for d in dims_tasa:
                conv[d][claves[d]] += 1
            dia, hora = _dia_hora(e.get("ts", ""))
            if dia >= 0:
                conv_dia[dia] += 1
            if hora >= 0:
                conv_hora[hora] += 1

    def tabla_tasa(dim: str) -> list[dict]:
        filas = []
        for clave, n_env in sorted(env[dim].items(), key=lambda kv: -kv[1]):
            if clave == "":
                continue
            c = conv[dim].get(clave, 0)
            filas.append({"clave": _rotular(dim, clave), "valor": clave,
                          "envios": n_env, "conversiones": c, "tasa": _tasa(n_env, c)})
        return filas

    def mejor_tasa(dim: str) -> dict | None:
        # Mayor tasa entre los que tienen muestra suficiente de ENVÍOS. Sin
        # nadie que llegue al mínimo, no se corona a ninguno (evita "100% con 1").
        candidatos = [f for f in tabla_tasa(dim) if f["envios"] >= MINIMO_PARA_RANKEAR]
        return max(candidatos, key=lambda f: (f["tasa"], f["envios"])) if candidatos else None

    def tabla_timing(cont: dict, dim: str) -> list[dict]:
        return [{"clave": _rotular(dim, k), "valor": k, "conversiones": v}
                for k, v in sorted(cont.items(), key=lambda kv: -kv[1])]

    def pico(cont: dict, dim: str) -> dict | None:
        # El bucket con MÁS conversiones, con un piso para no coronar un click
        # suelto. Es volumen de clicks, no una tasa.
        if not cont or max(cont.values()) < 3:
            return None
        k = max(cont, key=lambda x: cont[x])
        return {"clave": _rotular(dim, k), "valor": k, "conversiones": cont[k]}

    salida = {
        "programa": programa.strip().lower() or "todos",
        "envios": tot_env,
        "conversiones": tot_conv,
        "tasa_conversion": _tasa(tot_env, tot_conv),
        "por_programa": tabla_tasa("programa"),
        "por_segmento": tabla_tasa("segmento"),
        "por_canal": tabla_tasa("canal"),
        "por_nivel": tabla_tasa("nivel"),
        "por_pais": tabla_tasa("pais"),
        "por_dia": tabla_timing(conv_dia, "dia"),
        "por_hora": tabla_timing(conv_hora, "hora"),
        "mejor_segmento": mejor_tasa("segmento"),
        "mejor_canal": mejor_tasa("canal"),
        "mejor_nivel": mejor_tasa("nivel"),
        # día y hora son el PICO de conversiones (cuándo entra la gente), no
        # una tasa: la clave lo deja claro para la interfaz.
        "mejor_dia": pico(conv_dia, "dia"),
        "mejor_hora": pico(conv_hora, "hora"),
        "muestra_suficiente": tot_env >= MINIMO_PARA_RANKEAR,
    }
    if costo is not None and costo > 0:
        salida["costo"] = round(costo, 2)
        salida["cpm"] = round(costo / tot_env * 1000, 2) if tot_env else None
        salida["cpa"] = round(costo / tot_conv, 2) if tot_conv else None
    return salida


def _rotular(dim: str, clave) -> str:
    if dim == "dia" and isinstance(clave, int) and 0 <= clave < 7:
        return DIAS_ES[clave]
    if dim == "hora" and isinstance(clave, int) and clave >= 0:
        return f"{clave:02d}:00"
    return str(clave)


def borrar_todo() -> None:
    """Sólo para los tests y para el botón de 'reiniciar métricas'."""
    ruta = _ruta()
    with _lock:
        if os.path.exists(ruta):
            os.remove(ruta)
