#!/usr/bin/env python3
"""
Arma `INSTALADOR/OWNER/` — la carpeta del dueño, la que NO se publica.

    python3 packaging/armar_owner.py --codigo TU-CODIGO-LARGO

Sale de la metodología de MV Agendate IA, que separa las entregas en
`INSTALADOR/CLIENTE/` (lo que baja quien compra) y `INSTALADOR/OWNER/` (lo
del dueño), con un conversor que pasa una copia YA instalada a la edición
completa sin reinstalar 95 MB.

Dos diferencias con el de Agendate, las dos a propósito:

1. **El conversor busca solo dónde se instaló.** El de Agendate hay que
   copiarlo a mano adentro de la carpeta del programa; si no, avisa que no
   encontró nada. Acá el instalador deja ELEGIR la carpeta, así que el
   conversor mira el registro de Windows, las carpetas por defecto, el
   destino real de los accesos directos y recién por último la carpeta
   propia.

2. **Pide un código de dueño.** El conversor es la llave maestra del
   producto: convierte cualquier copia instalada en la edición completa. En
   Agendate se protege dejándolo sólo en el repositorio — pero ese repo hoy
   es público, y éste también, así que "no lo repartas" no alcanza: estaría
   publicado desde el día uno. Acá el .bat lleva horneado el SHA-256 del
   código (no el código), y sin él no toca nada. Por eso el .bat armado no se
   versiona: se arma en la máquina del dueño, con este script.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ / "packaging" / "bat" / "Convertir-a-edicion-dueno.bat"
DESTINO = RAIZ / "INSTALADOR" / "OWNER"
MARCADOR = "{{CODIGO_SHA256}}"

# Los artefactos de la edición owner, si el build los dejó en dist/. No es un
# error que falten: el conversor solo ya sirve para pasar una instalación
# existente a dueño, que es justamente para lo que existe.
ARTEFACTOS = ["MVClienteIA_Setup_owner.exe", "MVClienteIA_Portable_owner.zip",
              "MVClienteIA_BAT_owner.zip"]

LEEME = """MV Cliente IA - carpeta del DUENO
=================================

Lo que hay aca convierte cualquier copia instalada en la edicion completa
(sin clave, sin vencimiento). Por eso esta carpeta no se publica, no va a
la Release y no se versiona: el repositorio es publico.

  Convertir-a-edicion-dueno.bat
      Doble clic. Busca solo donde quedo instalado el programa -- registro
      de Windows, carpetas por defecto, accesos directos del escritorio y
      del menu Inicio -- y le escribe el sello de la edicion dueno.
      Pide tu codigo de dueno: si el archivo se filtra, sin el codigo no
      sirve. Corriendolo de nuevo ofrece volver a la edicion normal.

  MVClienteIA_Setup_owner.exe / _Portable_owner.zip / _BAT_owner.zip
      Las entregas de la edicion dueno ya armadas, si el build las dejo.
      Sirven para instalar de cero; el conversor sirve para no volver a
      bajar 95 MB cuando ya tenes el programa instalado.

Para rearmar esta carpeta:

  python3 packaging/armar_owner.py --codigo TU-CODIGO-LARGO
"""


def armar(codigo: str, destino: Path = DESTINO) -> Path:
    if len(codigo) < 12:
        # Un .bat filtrado deja probar el hash offline, sin límite de
        # intentos: un código corto se rompe en minutos con un diccionario.
        raise ValueError("El código de dueño tiene que tener al menos 12 "
                         "caracteres: el hash queda dentro del .bat y se "
                         "puede probar sin límite si el archivo se filtra")
    plantilla = PLANTILLA.read_text(encoding="utf-8")
    if MARCADOR not in plantilla:
        raise ValueError(f"La plantilla no tiene el marcador {MARCADOR}")

    hash_codigo = hashlib.sha256(codigo.encode()).hexdigest()
    destino.mkdir(parents=True, exist_ok=True)
    guion = destino / PLANTILLA.name
    # CRLF: un .bat con finales de línea de Unix falla en Windows de formas
    # que no dicen nada ("no se esperaba" a mitad de una etiqueta).
    guion.write_text(plantilla.replace(MARCADOR, hash_codigo),
                     encoding="ascii", newline="\r\n")

    (destino / "LEEME.txt").write_text(LEEME, encoding="ascii", newline="\r\n")

    copiados = []
    for nombre in ARTEFACTOS:
        origen = RAIZ / "dist" / nombre
        if origen.exists():
            shutil.copy2(origen, destino / nombre)
            copiados.append(nombre)
    return destino, copiados


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--codigo", required=True,
                   help="El código que te va a pedir el conversor. No se "
                        "guarda en ningún lado: dentro del .bat va su SHA-256.")
    p.add_argument("--destino", type=Path, default=DESTINO)
    args = p.parse_args(argv)

    try:
        destino, copiados = armar(args.codigo, args.destino)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print(f"OK: {destino}")
    print(f"  - {PLANTILLA.name} (con tu codigo horneado)")
    print("  - LEEME.txt")
    for c in copiados:
        print(f"  - {c}")
    if not copiados:
        print("  (sin instaladores owner en dist/: el conversor igual sirve)")
    print()
    print("Guarda el codigo: sin el, el conversor no convierte nada.")
    print("Esta carpeta NO se versiona (esta en .gitignore).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
