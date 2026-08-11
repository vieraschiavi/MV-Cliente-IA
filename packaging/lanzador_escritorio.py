"""
MV Cliente IA · lanzador de escritorio para la edición BAT
==========================================================
La edición BAT existe para las empresas que no dejan ejecutar un `.exe`.
Corre EXACTAMENTE el mismo programa que el instalador de Windows —el motor
FastAPI sirviendo la interfaz React— pero en el navegador que ya está
instalado, sin ningún ejecutable propio de por medio.

Toda la lógica vive acá y no en el `.bat` a propósito: en un `.bat` no se
puede testear nada, y esto se prueba en Linux con la misma suite que el resto
del producto. El `.bat` sólo tiene que encontrar Python y llamar a este
archivo.

Diferencia con `lanzador.py` (el que empaqueta PyInstaller): aquel recibe el
puerto de Electron, que es quien abre la ventana. Acá no hay Electron, así
que este archivo también busca el puerto, espera a que el motor conteste y
recién ahí abre el navegador. Abrirlo antes muestra un "no se puede acceder
al sitio" y el usuario cree que el programa no anda.
"""
from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# `datetime.UTC` (cliente_ia/licencia.py, cliente_ia/pipeline.py) existe recién
# desde 3.11. En 3.10 el programa importa y muere con ImportError a mitad de
# camino, que para el usuario es una ventana negra que se cierra sola.
VERSION_MINIMA = (3, 11)
PUERTO_DEFAULT = 8810
ESPERA_DEFAULT = 60.0


def version_soportada(version: tuple[int, ...] = ()) -> bool:
    return tuple(version or sys.version_info[:2]) >= VERSION_MINIMA


def texto_version_vieja(version: tuple[int, ...] = ()) -> str:
    v = tuple(version or sys.version_info[:2])
    return (
        f"MV Cliente IA necesita Python {VERSION_MINIMA[0]}.{VERSION_MINIMA[1]} "
        f"o más nuevo, y esta es la {v[0]}.{v[1]}.\n"
        "Instalá una versión al día desde https://www.python.org/downloads/ "
        "o desde la Microsoft Store (esa no pide permisos de administrador)."
    )


def puerto_libre(host: str = "127.0.0.1", preferido: int = PUERTO_DEFAULT) -> int:
    """El preferido si está libre; si no, uno que elija el sistema.

    Sin `SO_REUSEADDR` a propósito: acá se quiere saber si el puerto está
    realmente ocupado por otra aplicación, no reusar uno en TIME_WAIT.
    """
    with socket.socket() as s:
        try:
            s.bind((host, preferido))
            return preferido
        except OSError:
            pass
    with socket.socket() as s:
        s.bind((host, 0))
        return int(s.getsockname()[1])


def esperar_motor(url: str, espera: float = ESPERA_DEFAULT,
                  intervalo: float = 0.25) -> bool:
    """True cuando `/api/salud` contesta. Es lo que separa "todavía está
    arrancando" de "no arrancó": sin esto el navegador se abre contra un
    puerto muerto."""
    limite = time.monotonic() + espera
    while time.monotonic() < limite:
        try:
            with urllib.request.urlopen(f"{url}/api/salud", timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError, ValueError):
            pass
        time.sleep(intervalo)
    return False


def _abrir_cuando_este(url: str, espera: float) -> None:
    import webbrowser

    if not esperar_motor(url, espera):
        print(f"[MV Cliente IA] el motor no respondió en {espera:.0f}s; "
              f"abrí {url} a mano si la ventana no apareció", flush=True)
        return
    print(f"[MV Cliente IA] abriendo {url}", flush=True)
    try:
        webbrowser.open(url)
    except Exception as e:                                  # noqa: BLE001
        # Sin navegador por default (o una sesión sin escritorio) no es motivo
        # para tumbar el motor: la URL está impresa y se puede pegar a mano.
        print(f"[MV Cliente IA] no se pudo abrir el navegador solo ({e}); "
              f"entrá a {url}", flush=True)


def _servidor(host: str, puerto: int, silencioso: bool = False):
    import uvicorn

    from webapp.backend.api import app

    config = uvicorn.Config(app, host=host, port=puerto,
                            log_level="warning" if silencioso else "info")
    return uvicorn.Server(config)


def _banner(url: str, edicion: str, estado_txt: str) -> str:
    return "\n".join([
        "",
        "  ===========================================",
        "   MV Cliente IA",
        "  ===========================================",
        f"   Edición  : {edicion}",
        f"   Licencia : {estado_txt}",
        f"   Programa : {url}",
        "",
        "   Se abre en tu navegador. Para apagarlo,",
        "   cerrá esta ventana o apretá Ctrl+C.",
        "",
    ])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MV Cliente IA · edición BAT")
    ap.add_argument("--puerto", type=int, default=None)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-abrir", action="store_true",
                    help="no abrir el navegador (lo usa el CI)")
    ap.add_argument("--espera", type=float, default=ESPERA_DEFAULT)
    ap.add_argument("--diagnostico", action="store_true",
                    help="arranca, comprueba que el motor conteste y sale")
    args = ap.parse_args(argv)

    if not version_soportada():
        print(texto_version_vieja(), file=sys.stderr)
        return 2

    from cliente_ia import licencia

    puerto = args.puerto if args.puerto is not None else puerto_libre(args.host)
    url = f"http://{args.host}:{puerto}"

    est = licencia.estado()
    if not est.activa:
        estado_txt = est.motivo or "sin licencia activa"
    elif est.dias_restantes > 0:
        estado_txt = f"activa · quedan {est.dias_restantes} días"
    else:
        # La edición owner y las claves sin fecha devuelven -1: no es que
        # falten -1 días, es que no vencen.
        estado_txt = "activa · sin vencimiento"
    print(_banner(url, licencia.edicion(), estado_txt), flush=True)

    servidor = _servidor(args.host, puerto, silencioso=args.diagnostico)

    if args.diagnostico:
        hilo = threading.Thread(target=servidor.run, daemon=True)
        hilo.start()
        ok = esperar_motor(url, args.espera)
        servidor.should_exit = True
        hilo.join(timeout=10)
        print(f"[diagnóstico] motor responde: {'sí' if ok else 'NO'}", flush=True)
        return 0 if ok else 1

    if not args.no_abrir:
        threading.Thread(target=_abrir_cuando_este, args=(url, args.espera),
                         daemon=True).start()
    try:
        servidor.run()
    except KeyboardInterrupt:
        print("\n[MV Cliente IA] apagado.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
