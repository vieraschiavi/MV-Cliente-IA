"""
MV Cliente IA · métricas de envíos y conversión (backend)
==========================================================
Lo que Explee no te da y el usuario pidió: saber, **del lado del servidor**,
qué está funcionando. No cuántos correos mandaste —eso lo sabe cualquiera—
sino a QUÉ segmento, en qué DÍA y a qué HORA le fue mejor, y qué proporción
de esos envíos terminó en una visita a la web.

Cinco tipos de evento, en un JSONL que se agrega (nunca se reescribe):

- **envio**    — un mensaje que salió: programa (dominio del producto), canal
  (email/linkedin/x), segmento (sector del prospecto), nivel (la ola: local /
  regional / mundo), país, idioma, y el sello de tiempo.
- **apertura** — el correo se abrió. Llega por `/api/abierto`, el pixel de
  1×1 del HTML, con la MISMA meta que el enlace, así apertura y click se
  cruzan en las mismas dimensiones. Se cuentan aperturas únicas por nonce.
- **conversion** — alguien hizo click en el enlace del mensaje y entró a la
  web. Llega por `/api/ir`, el redirect firmado: sólo cuenta un click cuyo
  token FIRMAMOS nosotros, así que no se puede inflar la conversión a mano.
- **respuesta** — alguien contestó un correo nuestro. Lo cuenta
  `/api/respuestas`, leyendo por IMAP las CABECERAS de la bandeja del usuario
  (nunca el cuerpo) y cruzando el `In-Reply-To` contra los Message-ID que
  emitimos. La respuesta hereda la meta del envío original, así que se puede
  decir «fintech te responde y retail no», que es el número que sirve.
  Una por hilo: contestar tres veces sigue siendo UN prospecto que respondió.
- **visita**   — tráfico de la web, venga de donde venga. Llega por
  `/api/visita`, que dispara la propia landing. Es lo que le da escala al
  resto: sin esto, "10 clicks desde el correo" no dice si son el 90% del
  tráfico o el 3%. Sin cookie ni identificador: idioma y dominio de origen.

La tasa de respuesta se calcula sobre los envíos que llevan Message-ID, no
sobre todos: un envío viejo o de LinkedIn no se puede cruzar con la bandeja, y
meterlo en el denominador daría una tasa artificialmente baja.

`resumen()` cruza los cinco y arma el embudo —enviado → abierto → click →
respuesta— con
la tasa por programa, segmento, canal, ola y país, más el día y la hora en que
entra la gente. CPM y CPA salen sólo si se le pasa un costo: sin plata gastada
no hay "costo por mil" que inventar.

Honestidad de la tasa de apertura: el pixel sólo cuenta si el cliente de correo
baja las imágenes. Outlook las bloquea por defecto y Gmail las precarga por su
proxy, así que el número sirve para COMPARAR segmentos, asuntos y horarios
entre sí, no como cuenta absoluta de personas que leyeron. La interfaz lo dice.

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
import collections
import hashlib
import hmac
import json
import os
import secrets
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

# Techo del archivo. Sin esto, `/api/metricas/envios` (o el replay del enlace
# de conversión) puede escribir sin fin: en la edición instalada llenaría el
# disco, y `resumen()` relee el archivo entero en cada llamada, así que el
# costo de lectura también crecería sin límite. Al toparlo, se deja de
# agregar — perder una métrica es mejor que tumbar la máquina del cliente.
MAX_BYTES = int(os.getenv("MVCLIENTE_METRICAS_MAX_BYTES", str(20 * 1024 * 1024)))

# Nonces de conversión ya vistos, para no contar dos veces el MISMO click.
# El enlace del correo lleva un nonce único por envío; reproducirlo (el
# destinatario que recdcarga, o un atacante que repite el token que le llegó)
# no infla la conversión. Acotado en memoria para no crecer sin techo; se
# reinicia entre arranques, y el techo del archivo cubre el resto.
_NONCES_TOPE = 200_000
_nonces_vistos = None  # OrderedDict, se inicializa perezoso en `_nonce_nuevo`

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
        ruta = _ruta()
        # Techo de disco: si el archivo ya llegó al límite, no se agrega más.
        # Barato (getsize), y corta el llenado por spam o replay antes de que
        # importe.
        try:
            if os.path.exists(ruta) and os.path.getsize(ruta) >= MAX_BYTES:
                return
        except OSError:
            pass
        # `a` es atómico para líneas cortas en POSIX; el instalado es
        # monoproceso, así que no hay carrera real. No se reescribe el
        # archivo: un evento perdido es mejor que corromper el historial.
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(linea + "\n")


def _nonce_nuevo(nonce: str) -> bool:
    """True la primera vez que se ve un nonce; False si ya se contó. Acota el
    set para no crecer sin techo (descarta el más viejo)."""
    global _nonces_vistos
    if not nonce:
        return True                          # sin nonce no hay dedup (compat)
    with _lock:
        if _nonces_vistos is None:
            _nonces_vistos = collections.OrderedDict()
        if nonce in _nonces_vistos:
            return False
        _nonces_vistos[nonce] = True
        if len(_nonces_vistos) > _NONCES_TOPE:
            _nonces_vistos.popitem(last=False)
        return True


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
            # El Message-ID del correo, cuando lo hay. Es lo que después
            # permite reconocer una RESPUESTA en la bandeja de entrada: la
            # respuesta trae este id en `In-Reply-To`. Un envío sin `mid` se
            # cuenta igual, pero no es rastreable para respuestas — por eso
            # la tasa de respuesta se calcula sobre los que sí lo tienen.
            **({"mid": str(e["mid"])[:300]} if e.get("mid") else {}),
        })
        n += 1
    return n


def mensajes_rastreables(programa: str = "") -> dict[str, dict]:
    """Los envíos con Message-ID, indexados por id, con su meta.

    Es lo que `/api/respuestas` cruza contra la bandeja de entrada. Se
    devuelve la meta completa para poder atribuir la respuesta al mismo
    segmento/ola/país que el envío, sin guardar en ningún lado a quién se le
    escribió: el índice se arma leyendo el propio historial de métricas.
    """
    salida: dict[str, dict] = {}
    for e in _leer(programa):
        if e.get("tipo") == "envio" and e.get("mid"):
            salida[e["mid"]] = {k: e.get(k, "") for k in
                                ("programa", "canal", "segmento", "nivel",
                                 "pais", "idioma")}
    return salida


def registrar_respuesta(mid: str, meta: dict) -> bool:
    """Una respuesta a un correo nuestro. Una por hilo: si la persona contesta
    tres veces, sigue siendo UN prospecto que respondió, y contar tres daría
    una tasa de respuesta inflada."""
    if not _nonce_nuevo("r:" + str(mid or "")):
        return False
    _agregar({
        "tipo": "respuesta",
        "ts": _ts(meta.get("ts")),
        "mid": str(mid)[:300],
        "programa": str(meta.get("programa", "")).strip().lower(),
        "canal": str(meta.get("canal", "")).strip().lower(),
        "segmento": str(meta.get("segmento", "")).strip().lower(),
        "nivel": str(meta.get("nivel", "")).strip().lower(),
        "pais": str(meta.get("pais", "")).strip().upper()[:2],
        "idioma": str(meta.get("idioma", "")).strip().lower()[:2],
    })
    return True


def registrar_apertura(datos: dict) -> bool:
    """Cuenta una apertura de correo, salvo que su nonce ya se haya visto.

    Se cuentan aperturas ÚNICAS, no impresiones: el pixel se pide de nuevo
    cada vez que la persona vuelve a abrir el mensaje, y contar eso daría
    tasas de apertura por encima del 100%.

    Lo que esta métrica NO es: una verdad exacta. El pixel sólo se carga si el
    cliente de correo baja las imágenes. Outlook las bloquea por defecto (esas
    aperturas no se ven) y Gmail las precarga por su proxy (algunas se cuentan
    sin que nadie haya leído nada). Sirve para COMPARAR segmentos, asuntos y
    horarios entre sí, que es para lo que se usa; no para afirmar "45 personas
    leyeron el correo". La interfaz lo dice con todas las letras.
    """
    if not _nonce_nuevo("a:" + str(datos.get("nonce", ""))):
        return False
    _agregar({
        "tipo": "apertura",
        "ts": _ts(datos.get("ts")),
        "programa": str(datos.get("programa", "")).strip().lower(),
        "canal": str(datos.get("canal", "")).strip().lower(),
        "segmento": str(datos.get("segmento", "")).strip().lower(),
        "nivel": str(datos.get("nivel", "")).strip().lower(),
        "pais": str(datos.get("pais", "")).strip().upper()[:2],
        "idioma": str(datos.get("idioma", "")).strip().lower()[:2],
    })
    return True


def registrar_visita(datos: dict) -> bool:
    """Una visita a la web, la mande quien la mande.

    Es tráfico TOTAL, no sólo el que viene de los correos: la diferencia entre
    visitas y conversiones es justamente lo que entra por otro lado (buscador,
    redes, boca a boca). Sin eso, «100 clicks desde correo» no dice si son el
    90% del tráfico o el 3%.

    No hay cookie ni identificador de persona: se cuenta la visita con su
    idioma y de dónde vino, y nada más. No hace falta más para el KPI y evita
    convertir esto en un rastreador.
    """
    _agregar({
        "tipo": "visita",
        "ts": _ts(datos.get("ts")),
        "programa": str(datos.get("programa", "")).strip().lower(),
        "idioma": str(datos.get("idioma", "")).strip().lower()[:2],
        "origen": str(datos.get("origen", "")).strip().lower()[:60],
    })
    return True


def registrar_conversion(datos: dict) -> bool:
    """Cuenta una conversión, salvo que su nonce ya se haya visto (replay del
    mismo enlace). Devuelve True si contó, False si era repetida."""
    if not _nonce_nuevo(str(datos.get("nonce", ""))):
        return False
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
    return True


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
    Firmado: `/api/ir` sólo cuenta —y sólo redirige a— lo que salió de acá.

    Lleva un `nonce` único por enlace: así el mismo click no se cuenta dos
    veces (el destinatario que recarga, o alguien que repite el token que le
    llegó). Cada correo sale con su nonce, así que cuenta a lo sumo una
    conversión por envío, no importa cuántas veces se abra."""
    cuerpo = {"u": destino, "j": meta.get("nonce") or secrets.token_urlsafe(9),
              **{k: str(v) for k, v in meta.items() if v and k != "nonce"}}
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
# Pixel de apertura (mismo esquema de firma que el redirect)
# ---------------------------------------------------------------------------
def firmar_apertura(meta: dict) -> str:
    """Token del pixel. Va SIN `u`, que es lo que lo separa del token del
    redirect: `verificar_traqueo` exige destino, así que un token de apertura
    nunca puede usarse para hacer rebotar a nadie a ninguna parte."""
    cuerpo = {"a": 1, "j": meta.get("nonce") or secrets.token_urlsafe(9),
              **{k: str(v) for k, v in meta.items() if v and k != "nonce"}}
    crudo = json.dumps(cuerpo, separators=(",", ":"), sort_keys=True).encode()
    datos = base64.urlsafe_b64encode(crudo).decode().rstrip("=")
    return f"{datos}.{_firma(datos)}"


def verificar_apertura(token: str) -> dict | None:
    secreto = _secreto_traqueo()
    if not secreto or not token or token.count(".") != 1:
        return None
    datos, firma = token.split(".", 1)
    if not hmac.compare_digest(firma, _firma(datos)):
        return None
    try:
        cuerpo = json.loads(base64.urlsafe_b64decode(datos + "=" * (-len(datos) % 4)))
    except (ValueError, TypeError):
        return None
    return cuerpo if isinstance(cuerpo, dict) and cuerpo.get("a") else None


def url_de_apertura(base: str, meta: dict) -> str:
    """`<base>/api/abierto?t=<token>`, que es el `src` del pixel del correo."""
    return f"{base.rstrip('/')}/api/abierto?" + urlencode({"t": firmar_apertura(meta)})


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
    abre: dict[str, dict] = {d: defaultdict(int) for d in dims_tasa}
    conv_dia: dict[int, int] = defaultdict(int)
    conv_hora: dict[int, int] = defaultdict(int)
    visitas_origen: dict[str, int] = defaultdict(int)
    resp: dict[str, dict] = {d: defaultdict(int) for d in dims_tasa}
    # Denominador propio de la tasa de respuesta: sólo los envíos con
    # Message-ID se pueden cruzar con la bandeja. Dividir las respuestas por
    # TODOS los envíos daría una tasa artificialmente baja apenas haya un
    # envío viejo sin id.
    rastreables: dict[str, dict] = {d: defaultdict(int) for d in dims_tasa}
    tot_env = tot_conv = tot_abre = tot_visitas = tot_resp = tot_rastreables = 0

    for e in eventos:
        claves = {d: e.get(d, "") for d in dims_tasa}
        if e.get("tipo") == "envio":
            n = int(e.get("n", 1) or 1)
            tot_env += n
            for d in dims_tasa:
                env[d][claves[d]] += n
            if e.get("mid"):
                tot_rastreables += 1
                for d in dims_tasa:
                    rastreables[d][claves[d]] += 1
        elif e.get("tipo") == "respuesta":
            tot_resp += 1
            for d in dims_tasa:
                resp[d][claves[d]] += 1
        elif e.get("tipo") == "visita":
            tot_visitas += 1
            visitas_origen[e.get("origen", "") or "directo"] += 1
        elif e.get("tipo") == "apertura":
            tot_abre += 1
            for d in dims_tasa:
                abre[d][claves[d]] += 1
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
            a = abre[dim].get(clave, 0)
            rp = resp[dim].get(clave, 0)
            rast = rastreables[dim].get(clave, 0)
            filas.append({"clave": _rotular(dim, clave), "valor": clave,
                          "envios": n_env, "conversiones": c, "tasa": _tasa(n_env, c),
                          "aperturas": a, "tasa_apertura": _tasa(n_env, a),
                          "respuestas": rp, "tasa_respuesta": _tasa(rast, rp)})
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
        "aperturas": tot_abre,
        "tasa_apertura": _tasa(tot_env, tot_abre),
        # De los que abrieron, cuántos entraron. Es el KPI que separa "el
        # asunto no engancha" (poca apertura) de "el mensaje no convence"
        # (abren y no hacen click).
        "tasa_click_sobre_apertura": _tasa(tot_abre, tot_conv),
        "respuestas": tot_resp,
        # Sobre los rastreables, no sobre todos los envíos (ver arriba).
        "tasa_respuesta": _tasa(tot_rastreables, tot_resp),
        "rastreables": tot_rastreables,
        "visitas": tot_visitas,
        "por_origen": [{"clave": k, "valor": k, "visitas": v}
                       for k, v in sorted(visitas_origen.items(), key=lambda kv: -kv[1])],
        # Qué porción del tráfico de la web la trajo la prospección. Si da
        # bajo, la web vive de otra cosa y el outbound está pesando poco.
        "parte_del_trafico": _tasa(tot_visitas, tot_conv),
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
    global _nonces_vistos
    ruta = _ruta()
    with _lock:
        if os.path.exists(ruta):
            os.remove(ruta)
        _nonces_vistos = None                # también se olvidan los clicks vistos
