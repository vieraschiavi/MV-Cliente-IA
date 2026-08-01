"""
MV Cliente IA · proveedores de datos
=====================================
`construir(modo)` arma la cadena que corresponde:

| modo   | cadena                          | qué aporta cada uno                     |
|--------|---------------------------------|-----------------------------------------|
| demo   | demo                            | todo sintético, sin red, determinista   |
| web    | web → demo                      | fase 1 del sitio real, resto sintético  |
| llm    | web → llm → demo                | + competencia/campañas/empresas reales  |

`llm` cae solo a `web` si no hay `ANTHROPIC_API_KEY`: pedir el modo no es una
promesa de que la clave exista, y una corrida a medias es peor que una
corrida honesta en el modo que sí se puede.
"""
from __future__ import annotations

from .base import Proveedor, ProveedorEncadenado
from .demo import ProveedorDemo
from .web import ErrorWeb, ProveedorWeb

MODOS = ("demo", "web", "llm")


def construir(modo: str = "demo", idioma_base: str = "es") -> Proveedor:
    modo = (modo or "demo").lower()
    if modo not in MODOS:
        raise ValueError(f"Modo desconocido: {modo} (esperaba uno de {MODOS})")

    demo = ProveedorDemo(idioma_base)
    if modo == "demo":
        return demo

    web = ProveedorWeb(idioma_base)
    if modo == "web":
        return ProveedorEncadenado(web, demo)

    from .llm import ProveedorLLM, hay_clave
    if not hay_clave():
        return ProveedorEncadenado(web, demo)
    return ProveedorEncadenado(web, ProveedorLLM(idioma_base), demo)


def modo_efectivo(modo: str) -> str:
    """El modo que realmente va a correr, ya considerando si hay clave."""
    if modo == "llm":
        from .llm import hay_clave
        return "llm" if hay_clave() else "web"
    return modo


__all__ = ["MODOS", "ErrorWeb", "Proveedor", "ProveedorDemo", "ProveedorEncadenado",
           "ProveedorWeb", "construir", "modo_efectivo"]
