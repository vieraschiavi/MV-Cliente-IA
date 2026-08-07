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
sólo tiene el dueño (`MVCLIENTE_LICENCIA_SECRETO`). El programa **verifica**
la firma; no puede fabricar claves porque el secreto no viaja en el
instalador. Emitirlas es un comando del dueño (`python -m cliente_ia.licencia
emitir`).

Lo que esto NO es: una protección contra alguien que quiera crackear el
binario. Un `.exe` que corre en la máquina del cliente siempre se puede
parchear — eso vale para este programa y para cualquier otro. Es el candado
honesto que hace que el que paga tenga su clave y el que no, vea el aviso; no
una promesa de inviolabilidad que no podría cumplir.

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
def _secreto() -> bytes:
    return (os.getenv("MVCLIENTE_LICENCIA_SECRETO", "")
            or os.getenv("MVCLIENTE_OWNER", "")).encode()


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


def _clave_guardada() -> str:
    try:
        with open(rutas.dir_datos() / "licencia.json", encoding="utf-8") as f:
            return str(json.load(f).get("clave", ""))
    except (OSError, ValueError):
        return ""


def guardar_clave(clave: str) -> dict:
    """Guarda la clave si es válida. Devuelve el estado resultante."""
    r = verificar(clave)
    if not r["ok"]:
        return r
    destino = rutas.dir_datos() / "licencia.json"
    with open(destino, "w", encoding="utf-8") as f:
        json.dump({"clave": clave.strip()}, f)
    return r


# ---------------------------------------------------------------------------
# El estado que mira el resto del programa
# ---------------------------------------------------------------------------
def estado() -> Estado:
    ed = edicion()
    if ed == "owner":
        return Estado("owner", True, "", -1)

    if ed == "cliente":
        clave = _clave_guardada()
        if clave:
            r = verificar(clave)
            if r["ok"]:
                dias = -1
                if r.get("vence"):
                    dias = (datetime.fromisoformat(r["vence"]).date()
                            - datetime.now(UTC).date()).days
                return Estado("cliente", True, r.get("vence", ""), dias,
                              r.get("email", ""))
            return Estado("cliente", False, r.get("vence", ""), 0,
                          r.get("email", ""), r["motivo"])
        return Estado("cliente", False, "", 0, "",
                      "Pegá la clave de licencia que te llegó con la compra")

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
