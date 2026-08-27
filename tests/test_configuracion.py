"""`.env.example` es la documentación de qué se configura — y se desactualiza sola.

Un archivo de ejemplo que enumera variables a mano dura exactamente hasta el
próximo `os.getenv()` que alguien agregue sin acordarse de documentarlo. Ahí
deja de ser la lista de "todo lo configurable" y pasa a ser una lista
incompleta en la que igual se confía, que es peor que no tenerla.

Estos tests leen el CÓDIGO y comparan contra el archivo, en los dos sentidos.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EJEMPLO = RAIZ / ".env.example"

# Variables que NO son configuración del producto: las pone el sistema
# operativo, la plataforma de despliegue o una herramienta de desarrollo.
# Documentarlas en `.env.example` confundiría — nadie las carga en Vercel.
AJENAS = {
    "LOCALAPPDATA",          # Windows
    "XDG_DATA_HOME",         # Linux
    "VERCEL",                # la pone Vercel para decir que corre ahí
    "AWS_LAMBDA_FUNCTION_NAME",   # ídem, en Lambda
    "PLAYWRIGHT_BROWSERS_PATH",   # sólo para correr los tests de navegador
    "GH_TOKEN",              # lo inyecta GitHub Actions
    "RUNNER_TEMP",           # ídem
    "ANDROID_HOME",          # SDK de Android, para compilar el APK
}

CARPETAS_SALTEADAS = {"node_modules", ".git", "dist", "build", "graft",
                      "__pycache__", "public", "tests"}


def _variables_del_codigo() -> dict[str, str]:
    """Toda variable de entorno que el código lee de verdad → dónde."""
    encontradas: dict[str, str] = {}
    for p in RAIZ.rglob("*"):
        if not p.is_file() or p.suffix not in {".py", ".js", ".jsx"}:
            continue
        if any(s in p.parts for s in CARPETAS_SALTEADAS):
            continue
        texto = p.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(
                r'(?:getenv|environ\.get|environ\[)\(?["\']([A-Z][A-Z0-9_]+)["\']',
                texto):
            encontradas.setdefault(m.group(1), str(p.relative_to(RAIZ)))
    return encontradas


def _variables_del_ejemplo() -> set[str]:
    """Las que el archivo documenta: las que aparecen como `NOMBRE=`."""
    return set(re.findall(r"^([A-Z][A-Z0-9_]+)=",
                          EJEMPLO.read_text(encoding="utf-8"), re.MULTILINE))


def test_toda_variable_que_el_codigo_lee_esta_documentada():
    del_codigo = _variables_del_codigo()
    documentadas = _variables_del_ejemplo()
    faltan = {v: d for v, d in del_codigo.items()
              if v not in documentadas and v not in AJENAS}
    assert not faltan, (
        "Estas variables se leen en el código pero no están en .env.example, "
        "así que quien despliega no tiene forma de saber que existen:\n"
        + "\n".join(f"  {v}  (en {d})" for v, d in sorted(faltan.items())))


def test_el_ejemplo_no_documenta_variables_que_ya_nadie_lee():
    """El otro sentido: una variable que se sacó del código y quedó en el
    ejemplo hace perder tiempo configurando algo que no hace nada."""
    del_codigo = set(_variables_del_codigo())
    sobran = _variables_del_ejemplo() - del_codigo
    assert not sobran, (
        "Estas variables están documentadas en .env.example pero ya no las lee "
        "nadie:\n" + "\n".join(f"  {v}" for v in sorted(sobran)))


def test_el_ejemplo_no_lleva_ningun_valor():
    """El repositorio es PÚBLICO. Si alguien completa este archivo con sus
    claves de verdad y lo commitea, quedan en el historial para siempre."""
    for n, línea in enumerate(
            EJEMPLO.read_text(encoding="utf-8").splitlines(), 1):
        if re.match(r"^[A-Z][A-Z0-9_]+=", línea):
            nombre, valor = línea.split("=", 1)
            assert not valor.strip(), (
                f".env.example:{n}: «{nombre}» tiene un valor cargado. Este "
                f"archivo documenta NOMBRES, nunca valores.")


def test_las_variables_del_camino_de_pago_estan_documentadas():
    """Las que, si faltan, hacen que se cobre y no se entregue nada. Se
    nombran una por una a propósito: son las que rompen una venta."""
    documentadas = _variables_del_ejemplo()
    for clave in ("MERCADOPAGO_ACCESS_TOKEN", "MERCADOPAGO_WEBHOOK_SECRET",
                  "MVCLIENTE_LICENCIA_SECRETO", "MVCLIENTE_SMTP_HOST",
                  "MVCLIENTE_SMTP_USUARIO", "MVCLIENTE_SMTP_CLAVE"):
        assert clave in documentadas, f"falta {clave} en .env.example"
