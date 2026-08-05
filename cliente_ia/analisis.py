"""
MV Cliente IA · análisis de negocio (pestaña Análisis)
======================================================
Dos mitades deliberadamente separadas, para no vestir de dato lo que no lo es:

1. **La financiera es matemática pura** sobre los números que ingresa el
   usuario (precio, costos, adquisición, churn, ads). Acá no opina ningún
   modelo: los tres escenarios aplican multiplicadores fijos y DECLARADOS
   sobre esos números, y los multiplicadores viajan en la respuesta para que
   la interfaz los muestre como supuestos, no como verdades.
2. **La cualitativa (probabilidad de éxito, mercado potencial, FODA de la
   competencia) sólo existe con IA y con el texto real del sitio.** Sin
   clave no se inventa nada: la sección vuelve vacía con su aviso.
"""
from __future__ import annotations

import json

from . import geo

# Multiplicadores por escenario sobre los números DEL USUARIO. Son supuestos
# a la vista, no predicciones: pesimista consigue la mitad de clientes y
# pierde 1.5× más; optimista consigue 1.5× y retiene mejor.
SUPUESTOS = {
    "pesimista": {"adquisicion": 0.5, "churn": 1.5},
    "base": {"adquisicion": 1.0, "churn": 1.0},
    "optimista": {"adquisicion": 1.5, "churn": 0.7},
}
MESES = (3, 6, 9, 12, 18, 24)


def proyectar(precio: float, nuevos_por_mes: float, churn_pct: float,
              gasto_fijo: float, costo_por_cliente: float = 0.0,
              gasto_ads: float = 0.0, cac: float = 0.0,
              clientes_iniciales: float = 0.0) -> dict:
    """Proyección mensual de clientes e ingresos, con y sin publicidad, en
    los tres escenarios. Todo en la misma moneda en que vengan los campos."""

    def _serie(con_ads: bool, factores: dict) -> dict:
        churn = min(0.99, max(0.0, churn_pct / 100.0 * factores["churn"]))
        nuevos = max(0.0, nuevos_por_mes) * factores["adquisicion"]
        if con_ads and cac > 0:
            # Con ads entran además gasto_ads/CAC clientes por mes; el CAC lo
            # puso el usuario, el escenario sólo lo escala igual que al resto.
            nuevos += gasto_ads / cac * factores["adquisicion"]
        clientes = float(clientes_iniciales)
        filas, acumulado, equilibrio = [], 0.0, None
        for mes in range(1, max(MESES) + 1):
            clientes = clientes * (1 - churn) + nuevos
            ingresos = clientes * precio
            gastos = gasto_fijo + clientes * costo_por_cliente \
                + (gasto_ads if con_ads else 0.0)
            neto = ingresos - gastos
            acumulado += neto
            if equilibrio is None and neto >= 0:
                equilibrio = mes
            if mes in MESES:
                # Desglose completo: ventas y cada componente del gasto por
                # separado — un "gastos: 800" sin abrir no deja ver qué pesa.
                filas.append({
                    "mes": mes,
                    "clientes": round(clientes),
                    "ingresos": round(ingresos),
                    "gasto_fijo": round(gasto_fijo),
                    "gasto_variable": round(clientes * costo_por_cliente),
                    "gasto_ads": round(gasto_ads if con_ads else 0.0),
                    "gastos": round(gastos),
                    "neto_mes": round(neto),
                    "neto_acumulado": round(acumulado),
                })
        return {"filas": filas, "equilibrio_mes": equilibrio}

    return {
        "supuestos": SUPUESTOS,
        "escenarios": {
            nombre: {"sin_ads": _serie(False, f), "con_ads": _serie(True, f)}
            for nombre, f in SUPUESTOS.items()
        },
    }


# ---------------------------------------------------------------------------
# Análisis cualitativo con IA
# ---------------------------------------------------------------------------
NOMBRE_IDIOMA = {"es": "español", "pt": "portugués (Brasil)", "en": "inglés"}


def cualitativo(llm, empresa: dict, competidores: list[dict],
                mercado: str = "todos", idioma: str = "es") -> dict:
    """Le pide al modelo el análisis de éxito/mercado/FODA basado en el texto
    real del sitio y los competidores YA identificados en la corrida. `llm`
    es un ProveedorLLM ya construido (con la clave del usuario)."""
    from .proveedores.llm import ErrorLLM, _json_del_texto

    cod = str(empresa.get("pais") or "UY")
    pais = geo.nombre_pais(cod, idioma)
    region = geo.nombre_region(geo.region_de(cod), idioma)
    resumen = str(empresa.get("resumen_sitio") or "")[:2000]
    rivales = [
        {"nombre": c.get("nombre", ""), "pais": c.get("pais", ""),
         "posicionamiento": c.get("posicionamiento", "")}
        for c in competidores[:8] if c.get("nombre")
    ]
    prompt = (
        "Sos analista de negocio. Analizá la viabilidad de este producto con "
        "lo que hay acá — y SOLO con lo que hay acá: si un punto no se puede "
        "sostener con esta información, decí que falta información en vez de "
        "rellenar.\n\n"
        f"Producto: {empresa.get('nombre', '')} ({empresa.get('dominio', '')}), "
        f"con base en {pais}.\n"
        + (f"Texto real del sitio:\n{resumen}\n\n" if resumen else "")
        + (f"Competidores identificados: {json.dumps(rivales, ensure_ascii=False)}\n\n"
           if rivales else "Sin competidores identificados en la corrida.\n\n")
        + f"El análisis se escribe COMPLETO en {NOMBRE_IDIOMA.get(idioma, 'español')}. "
        f"El foco es proporcional: primero y con más profundidad {pais} (su "
        f"mercado de origen), después el resto de {region}, después el resto "
        "del mundo.\n\n"
        "Devolvé SOLO un objeto JSON con esta forma exacta:\n"
        "{\n"
        '  "probabilidad_exito": 0-100,\n'
        '  "veredicto": "2-3 frases: por qué esa probabilidad",\n'
        '  "mercado_potencial": {"local": "...", "regional": "...", "mundo": "..."},\n'
        '  "foda": [{"competidor": "...", "fortalezas": ["..."], "debilidades": ["..."],\n'
        '            "oportunidades": ["..."], "amenazas": ["..."]}],\n'
        '  "riesgos": ["los 3-5 riesgos principales del negocio"]\n'
        "}\n"
        "En `foda` analizá hasta 5 competidores, los del país de origen "
        "primero: fortalezas/debilidades DEL COMPETIDOR y oportunidades/"
        "amenazas QUE LE GENERAN a este producto."
    )
    datos = _json_del_texto(llm._pedir(prompt, 10000))
    if not isinstance(datos, dict):
        raise ErrorLLM("El análisis no volvió con la forma esperada")

    def _lista(x, tope=6):
        return [str(i) for i in x][:tope] if isinstance(x, list) else []

    mp = datos.get("mercado_potencial") or {}
    return {
        "probabilidad_exito": max(0, min(100, int(datos.get("probabilidad_exito") or 0))),
        "veredicto": str(datos.get("veredicto", "")).strip(),
        "mercado_potencial": {
            "local": str(mp.get("local", "")).strip(),
            # El modelo puede contestar con el nombre viejo de la ola.
            "regional": str(mp.get("regional") or mp.get("latam") or "").strip(),
            "mundo": str(mp.get("mundo", "")).strip(),
        },
        "foda": [
            {
                "competidor": str(f.get("competidor", "")).strip(),
                "fortalezas": _lista(f.get("fortalezas")),
                "debilidades": _lista(f.get("debilidades")),
                "oportunidades": _lista(f.get("oportunidades")),
                "amenazas": _lista(f.get("amenazas")),
            }
            for f in (datos.get("foda") or []) if isinstance(f, dict)
        ][:5],
        "riesgos": _lista(datos.get("riesgos"), 5),
    }
