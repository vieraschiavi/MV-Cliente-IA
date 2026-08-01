"""
MV Cliente IA · scoring de prospectos y decisores
==================================================
El score decide en qué orden se trabaja la lista. Es una fórmula explícita
—no un modelo entrenado— porque tiene que poder explicarse en una llamada de
ventas: cada punto sale de algo que el usuario puede ver en la ficha.

    score = 100 · ajuste_icp · peso_geográfico

`ajuste_icp` (0..1) combina cuatro señales, con estos pesos:

| señal              | peso | de dónde sale                                    |
|--------------------|------|--------------------------------------------------|
| sector             | 0.40 | el sector del prospecto está en el ICP de fase 1 |
| tamaño             | 0.25 | empleados dentro del rango objetivo              |
| señales de compra  | 0.25 | hechos con fecha: contrataron, expandieron, etc. |
| solapamiento comp. | 0.10 | usa/evalúa un competidor conocido                |

`peso_geográfico` es 1.00 en Uruguay, 0.72 en LATAM y 0.45 en el resto del
mundo (ver `cliente_ia.geo`). Es lo que hace que un prospecto uruguayo bueno
quede siempre por delante de uno mexicano igual de bueno, sin tener que
filtrar por país a mano.
"""
from __future__ import annotations

import re

from . import geo
from .modelos import Decisor, Empresa, Prospecto

PESO_SECTOR = 0.40
PESO_TAMANO = 0.25
PESO_SENALES = 0.25
PESO_COMPETENCIA = 0.10

# Cuánto suma cada señal de compra. Tope: 1.0 (tres señales ya saturan).
VALOR_SENAL = 0.34

# Seniority del decisor → cuánto pesa que sea esa persona la que contesta.
PESO_SENIORITY = {
    "c-level": 1.00,
    "director": 0.85,
    "gerente": 0.70,
    "jefe": 0.55,
    "analista": 0.35,
}


def _normalizar(texto: str) -> str:
    t = (texto or "").lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9 ]+", " ", t)


def ajuste_sector(sector: str, sectores_objetivo: list[str]) -> float:
    """1.0 si el sector es uno de los del ICP; 0.5 si comparte palabras; 0.15 si no."""
    if not sectores_objetivo:
        return 0.5
    s = _normalizar(sector)
    objetivos = [_normalizar(x) for x in sectores_objetivo]
    if s in objetivos:
        return 1.0
    palabras = {p for p in s.split() if len(p) > 3}
    for o in objetivos:
        if palabras & {p for p in o.split() if len(p) > 3}:
            return 0.5
    return 0.15


def _rango_tamano(tamano_objetivo: str) -> tuple[int, int]:
    """Lee '50-5000 empleados' → (50, 5000). Sin rango legible: (10, 20000)."""
    nums = [int(n) for n in re.findall(r"\d+", tamano_objetivo or "")]
    if len(nums) >= 2:
        return nums[0], nums[1]
    if len(nums) == 1:
        return nums[0], nums[0] * 50
    return 10, 20000


def ajuste_tamano(empleados: int, tamano_objetivo: str) -> float:
    """1.0 dentro del rango; cae de forma suave a medida que se aleja."""
    if not empleados:
        return 0.4                        # sin dato: ni premio ni castigo fuerte
    lo, hi = _rango_tamano(tamano_objetivo)
    if lo <= empleados <= hi:
        return 1.0
    if empleados < lo:
        return max(0.15, empleados / lo)
    return max(0.15, hi / empleados)


def ajuste_senales(senales: list[str]) -> float:
    return min(1.0, len(senales or []) * VALOR_SENAL)


def ajuste_competencia(senales: list[str], competidores: list[str]) -> float:
    """1.0 si alguna señal menciona a un competidor conocido (está en mercado)."""
    if not competidores:
        return 0.0
    texto = _normalizar(" ".join(senales or []))
    for c in competidores:
        raiz = _normalizar(c).split(" ")[0]
        if raiz and raiz in texto:
            return 1.0
    return 0.0


def ajuste_icp(prospecto: Prospecto, empresa: Empresa,
               competidores: list[str] | None = None) -> float:
    """Las cuatro señales combinadas, antes del peso geográfico (0..1)."""
    return (
        PESO_SECTOR * ajuste_sector(prospecto.sector, empresa.sectores_objetivo)
        + PESO_TAMANO * ajuste_tamano(prospecto.empleados, empresa.tamano_objetivo)
        + PESO_SENALES * ajuste_senales(prospecto.senales)
        + PESO_COMPETENCIA * ajuste_competencia(prospecto.senales, competidores or [])
    )


def puntuar_prospecto(prospecto: Prospecto, empresa: Empresa,
                      competidores: list[str] | None = None) -> Prospecto:
    """Completa score, ajuste_icp, prioridad, nivel e idioma. Muta y devuelve."""
    pais = geo.obtener(prospecto.pais)
    prospecto.ajuste_icp = round(ajuste_icp(prospecto, empresa, competidores), 4)
    prospecto.score = round(100.0 * prospecto.ajuste_icp * pais.peso, 2)
    prospecto.prioridad = pais.prioridad
    prospecto.nivel = pais.nivel
    prospecto.idioma = geo.idioma_de(prospecto.pais)
    return prospecto


def puntuar_decisor(decisor: Decisor, prospecto: Prospecto) -> Decisor:
    """El decisor hereda el score de su empresa, ajustado por seniority."""
    peso = PESO_SENIORITY.get((decisor.seniority or "").lower(), 0.5)
    decisor.score = round(prospecto.score * peso, 2)
    decisor.idioma = geo.idioma_de(decisor.pais or prospecto.pais)
    return decisor


def ordenar_prospectos(prospectos: list[Prospecto]) -> list[Prospecto]:
    """
    Uruguay primero, después LATAM, después el mundo; dentro de cada ola, por
    score. Se ordena por prioridad Y por score: el score ya lleva el peso
    geográfico, pero ordenar primero por prioridad garantiza que ninguna
    combinación de pesos pueda colar un prospecto del mundo antes que uno
    uruguayo — la regla del producto no depende de la calibración.
    """
    return sorted(prospectos, key=lambda p: (p.prioridad, -p.score, p.nombre))


def ordenar_decisores(decisores: list[Decisor]) -> list[Decisor]:
    return sorted(decisores, key=lambda d: (geo.prioridad_de(d.pais), -d.score, d.nombre))
