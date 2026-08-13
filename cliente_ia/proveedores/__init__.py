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


def construir(modo: str = "demo", idioma_base: str = "es",
              clave_ia: str = "", proveedor_ia: str = "claude",
              endpoint_ia: str = "", mercado: str = "todos",
              pais_base: str = "", modelo_ia: str = "") -> Proveedor:
    """`clave_ia` es la clave que el usuario pegó en la interfaz: vale para
    esta corrida y nada más. Nunca se guarda ni se escribe en un log.
    `proveedor_ia` elige el modelo detrás: claude, openai, gemini, copilot
    (Azure OpenAI, que además necesita `endpoint_ia`) o grok. `modelo_ia` es
    el modelo puntual dentro de ese proveedor que el usuario eligió en
    Configuración — vacío usa el default del servidor para ese proveedor.
    `mercado` y `pais_base` viajan al LLM para que la competencia se busque
    en el país que eligió el cliente y no en uno cableado."""
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
    if not clave_ia and not hay_clave():
        return ProveedorEncadenado(web, demo)
    llm = ProveedorLLM(idioma_base, clave=clave_ia,
                       proveedor=proveedor_ia if clave_ia else "claude",
                       endpoint=endpoint_ia, mercado=mercado,
                       pais_base=pais_base,
                       modelo=modelo_ia if clave_ia else "")
    # `decisivo`: el usuario pidió IA por nombre. Si la IA falla en una fase
    # que implementa, la corrida falla con el motivo a la vista — no se
    # rellena con datos sintéticos. El demo queda en la cadena SÓLO para lo
    # que el LLM no hace a propósito (decisores: organizaciones sí, personas
    # jamás — regla 6).
    return ProveedorEncadenado(web, llm, demo, decisivo=llm)


def modo_efectivo(modo: str, clave_ia: str = "") -> str:
    """El modo que realmente va a correr, ya considerando si hay clave."""
    if modo == "llm":
        from .llm import hay_clave
        return "llm" if (clave_ia or hay_clave()) else "web"
    return modo


__all__ = ["MODOS", "ErrorWeb", "Proveedor", "ProveedorDemo", "ProveedorEncadenado",
           "ProveedorWeb", "construir", "modo_efectivo"]
