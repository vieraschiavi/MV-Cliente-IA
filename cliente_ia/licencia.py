"""
MV Cliente IA · licencias del programa de escritorio
=====================================================
Tres ediciones del MISMO programa. Lo que cambia es una línea que se hornea
al construir (`MVCLIENTE_EDICION`), no el código:

| Edición   | Quién la baja                  | Qué hace |
|-----------|--------------------------------|----------|
| `demo`    | cualquiera, desde la landing   | 14 días de prueba con todo abierto; vencida, sólo queda el modo demo sintético |
| `cliente` | quien pagó                     | pide la clave de licencia una vez; con clave válida no vence hasta la fecha que diga la clave |
| `owner`   | sólo el dueño, del repo privado| sin clave y sin vencimiento |

Por qué así y no de otra forma
------------------------------
La clave de licencia es un texto firmado con HMAC-SHA256 sobre un secreto que
existe en dos lugares: la máquina del dueño (para emitir) y el servidor (para
validar). **Nunca dentro de un instalador.**

Eso obliga a que el programa instalado active **en línea**: manda la clave a
`/api/licencia/validar` y guarda el resultado. Es a propósito. Hornear el
secreto en el `.exe` habría evitado la conexión, pero cualquiera que abriera
el binario con un editor hexadecimal podría emitirse claves ilimitadas — y
convertiría en mentira la única promesa que vale acá.

Después de activar, el programa anda **sin conexión**: se guarda el resultado
de la validación. El vencimiento igual se vuelve a mirar contra el reloj en
cada arranque, así que una licencia de un año no queda abierta dos.

Lo que esto NO es: una protección contra alguien que quiera crackear el
binario. Un `.exe` que corre en la máquina del cliente siempre se puede
parchear, y el archivo de activación que queda en disco se puede editar. Eso
vale para este programa y para cualquier otro que no consulte al servidor en
cada uso. Es el candado honesto que hace que el que paga tenga su clave y el
que no, vea el aviso; no una promesa de inviolabilidad que no podría cumplir.

Y la edición `owner` lleva el permiso adentro: su seguridad es que **el
repositorio es privado**. Si ese `.exe` se filtra, quien lo tenga tiene la
edición completa. Está dicho en el LEEME de `INSTALADOR/` para que la decisión
de compartirlo sea consciente.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from . import rutas

EDICIONES = ("demo", "cliente", "owner")
DIAS_DEMO = 14

# El archivo que hornea el instalador. Va al lado del ejecutable empaquetado
# (no en la carpeta de datos del usuario): la edición es del INSTALADOR, no
# del perfil de quien lo usa — si viviera en los datos, un usuario podría
# ascenderse de demo a owner editando un JSON.
NOMBRE_SELLO = "edicion.json"


@dataclass(frozen=True)
class Estado:
    edicion: str
    activa: bool                 # ¿puede usar las búsquedas reales?
    vence: str                   # ISO corto, "" = no vence
    dias_restantes: int          # -1 = no vence
    email: str = ""              # a nombre de quién está la licencia
    motivo: str = ""             # por qué no está activa, para mostrar

    def a_dict(self) -> dict:
        return {"edicion": self.edicion, "activa": self.activa,
                "vence": self.vence, "dias_restantes": self.dias_restantes,
                "email": self.email, "motivo": self.motivo}


# ---------------------------------------------------------------------------
# Edición horneada
# ---------------------------------------------------------------------------
def _ruta_sello() -> os.PathLike | None:
    """Dónde dejó el instalador el sello de edición."""
    import sys
    from pathlib import Path

    candidatos = []
    if getattr(sys, "frozen", False):
        # PyInstaller onedir: el sello viaja al lado del ejecutable.
        candidatos.append(Path(sys.executable).resolve().parent / NOMBRE_SELLO)
        interno = getattr(sys, "_MEIPASS", "")
        if interno:
            candidatos.append(Path(interno) / NOMBRE_SELLO)
    candidatos.append(rutas.RAIZ / "packaging" / NOMBRE_SELLO)
    for c in candidatos:
        if c.exists():
            return c
    return None


def edicion() -> str:
    """La edición de ESTA copia. Sin sello ni variable: `demo`, que es el
    default seguro — nunca abrir de más por un archivo que falta."""
    de_entorno = (os.getenv("MVCLIENTE_EDICION") or "").strip().lower()
    if de_entorno in EDICIONES:
        return de_entorno
    ruta = _ruta_sello()
    if ruta:
        try:
            with open(ruta, encoding="utf-8") as f:
                marcada = str(json.load(f).get("edicion", "")).strip().lower()
            if marcada in EDICIONES:
                return marcada
        except (OSError, ValueError):
            pass
    return "demo"


def _instalada_el() -> datetime:
    """Cuándo se usó por primera vez esta copia. El archivo se crea solo la
    primera vez; borrarlo reinicia la prueba, y está bien: el candado real de
    la versión paga es la clave, no el reloj de la demo."""
    marca = rutas.dir_datos() / "primera_vez.json"
    ahora = datetime.now(UTC)
    try:
        with open(marca, encoding="utf-8") as f:
            return datetime.fromisoformat(json.load(f)["fecha"])
    except (OSError, ValueError, KeyError):
        try:
            with open(marca, "w", encoding="utf-8") as f:
                json.dump({"fecha": ahora.isoformat()}, f)
        except OSError:
            pass
        return ahora


# ---------------------------------------------------------------------------
# Claves de licencia
# ---------------------------------------------------------------------------
# Dónde se validan las claves cuando el programa NO tiene el secreto — que es
# el caso de todos los instaladores. Se puede apuntar a un servidor propio con
# `MVCLIENTE_URL_LICENCIAS`.
URL_VALIDACION = os.getenv("MVCLIENTE_URL_LICENCIAS",
                           "https://mv-cliente-ia.vercel.app")
TIMEOUT_VALIDACION = 20


def _secreto() -> bytes:
    """El secreto de firma. Existe en la máquina del dueño y en el servidor
    (variable de entorno); **nunca** en un instalador."""
    return (os.getenv("MVCLIENTE_LICENCIA_SECRETO", "")
            or os.getenv("MVCLIENTE_OWNER", "")).encode()


def _validar_en_linea(clave: str) -> dict:
    """Valida contra el servidor, que sí tiene el secreto.

    Es el camino normal del programa instalado. La alternativa —hornear el
    secreto adentro del .exe— dejaría a cualquiera que abra el binario con un
    editor hexadecimal emitiendo claves ilimitadas, y además volvería mentira
    la única promesa que vale acá: que el secreto no viaja.

    A cambio, activar pide internet una vez. Después queda guardada y el
    programa anda sin conexión.
    """
    import json as _json
    import urllib.error
    import urllib.request

    cuerpo = _json.dumps({"clave": clave}).encode()
    peticion = urllib.request.Request(
        f"{URL_VALIDACION.rstrip('/')}/api/licencia/validar", data=cuerpo,
        headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_VALIDACION) as r:
            return _json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return _json.loads(e.read().decode())
        except Exception:                                # noqa: BLE001
            return {"ok": False, "motivo": f"El servidor respondió {e.code}"}
    except Exception:                                    # noqa: BLE001
        return {"ok": False,
                "motivo": "No se pudo contactar al servidor para activar la "
                          "licencia. Revisá tu conexión y probá de nuevo."}


def emitir(email: str, meses: int = 12, secreto: str = "") -> str:
    """Fabrica una clave para un comprador. Es un comando del DUEÑO: necesita
    el secreto, que no viaja en ningún instalador."""
    llave = secreto.encode() if secreto else _secreto()
    if not llave:
        raise ValueError("Falta MVCLIENTE_LICENCIA_SECRETO para firmar")
    vence = (datetime.now(UTC) + timedelta(days=31 * meses)).date().isoformat()
    cuerpo = json.dumps({"email": email.strip().lower(), "vence": vence},
                        separators=(",", ":"), sort_keys=True)
    datos = base64.urlsafe_b64encode(cuerpo.encode()).decode().rstrip("=")
    firma = base64.urlsafe_b64encode(
        hmac.new(llave, cuerpo.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")[:32]
    return f"{datos}.{firma}"


def verificar(clave: str, secreto: str = "") -> dict:
    """Valida una clave. Devuelve {ok, email, vence, motivo}."""
    llave = secreto.encode() if secreto else _secreto()
    if not llave:
        return {"ok": False, "motivo": "El programa no tiene con qué verificar la clave"}
    partes = (clave or "").strip().split(".")
    if len(partes) != 2:
        return {"ok": False, "motivo": "La clave no tiene el formato esperado"}
    datos, firma = partes
    try:
        cuerpo = base64.urlsafe_b64decode(datos + "=" * (-len(datos) % 4))
        contenido = json.loads(cuerpo)
    except (ValueError, TypeError):
        return {"ok": False, "motivo": "La clave está incompleta o mal copiada"}
    esperada = base64.urlsafe_b64encode(
        hmac.new(llave, cuerpo, hashlib.sha256).digest()).decode().rstrip("=")[:32]
    if not hmac.compare_digest(firma, esperada):
        return {"ok": False, "motivo": "La clave no es válida para este producto"}
    vence = str(contenido.get("vence", ""))
    if vence and vence < datetime.now(UTC).date().isoformat():
        return {"ok": False, "vence": vence, "email": contenido.get("email", ""),
                "motivo": f"La licencia venció el {vence}"}
    return {"ok": True, "email": contenido.get("email", ""), "vence": vence,
            "motivo": ""}


def _guardado() -> dict:
    try:
        with open(rutas.dir_datos() / "licencia.json", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def comprobar(clave: str) -> dict:
    """Valida una clave por el camino que corresponda: local si esta máquina
    tiene el secreto (el dueño, el servidor, los tests); si no, contra el
    servidor."""
    if _secreto():
        return verificar(clave)
    return _validar_en_linea(clave)


def guardar_clave(clave: str) -> dict:
    """Activa la licencia: valida y, si pasa, la guarda junto con lo que dijo
    la validación (correo y vencimiento).

    Se guarda el RESULTADO además de la clave para que el programa arranque
    sin conexión: volver a llamar al servidor en cada inicio dejaría al
    cliente sin producto cada vez que se le cae internet.
    """
    r = comprobar(clave)
    if not r.get("ok"):
        return r
    destino = rutas.dir_datos() / "licencia.json"
    with open(destino, "w", encoding="utf-8") as f:
        json.dump({"clave": clave.strip(), "email": r.get("email", ""),
                   "vence": r.get("vence", ""),
                   "activada": datetime.now(UTC).date().isoformat()}, f)
    return r


# ---------------------------------------------------------------------------
# El estado que mira el resto del programa
# ---------------------------------------------------------------------------
def estado() -> Estado:
    ed = edicion()
    if ed == "owner":
        return Estado("owner", True, "", -1)

    if ed == "cliente":
        guardado = _guardado()
        if not guardado.get("clave"):
            return Estado("cliente", False, "", 0, "",
                          "Pegá la clave de licencia que te llegó con la compra")
        # Con el secreto a mano se revalida la firma; sin él (el instalador)
        # vale lo que quedó guardado en la activación. El vencimiento SIEMPRE
        # se vuelve a mirar contra el reloj: una licencia de un año no puede
        # seguir abierta dos años porque la activación fue offline.
        if _secreto():
            r = verificar(guardado["clave"])
            if not r["ok"]:
                return Estado("cliente", False, r.get("vence", ""), 0,
                              r.get("email", ""), r["motivo"])
            vence, email = r.get("vence", ""), r.get("email", "")
        else:
            vence, email = guardado.get("vence", ""), guardado.get("email", "")
        if vence and vence < datetime.now(UTC).date().isoformat():
            return Estado("cliente", False, vence, 0, email,
                          f"La licencia venció el {vence}. Renovala para seguir "
                          "usando las búsquedas reales.")
        dias = -1
        if vence:
            dias = (datetime.fromisoformat(vence).date()
                    - datetime.now(UTC).date()).days
        return Estado("cliente", True, vence, dias, email)

    # demo: 14 días desde el primer arranque
    vence_dt = _instalada_el() + timedelta(days=DIAS_DEMO)
    dias = (vence_dt.date() - datetime.now(UTC).date()).days
    if dias >= 0:
        return Estado("demo", True, vence_dt.date().isoformat(), dias)
    return Estado("demo", False, vence_dt.date().isoformat(), 0, "",
                  "La prueba de 14 días terminó. Comprá la licencia para seguir "
                  "usando las búsquedas reales.")


def _cli() -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m cliente_ia.licencia",
        description="Emitir y verificar claves de licencia (comando del dueño)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("emitir", help="Fabricar la clave de un comprador")
    e.add_argument("--email", required=True)
    e.add_argument("--meses", type=int, default=12)
    e.add_argument("--secreto", default="", help="Por defecto, MVCLIENTE_LICENCIA_SECRETO")

    v = sub.add_parser("verificar", help="Comprobar una clave")
    v.add_argument("clave")
    v.add_argument("--secreto", default="")

    sub.add_parser("estado", help="Qué edición y qué licencia ve esta copia")

    args = ap.parse_args()
    if args.cmd == "emitir":
        clave = emitir(args.email, args.meses, args.secreto)
        print(clave)
        print(f"\n  para: {args.email}\n  vence: "
              f"{verificar(clave, args.secreto)['vence']}")
    elif args.cmd == "verificar":
        r = verificar(args.clave, args.secreto)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["ok"] else 1
    else:
        print(json.dumps(estado().a_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
