"""
Robustez ante salida del modelo con formas raras, y de los export ante
cuerpos no confiables.

Todos vienen de la auditoría de correctitud: `int()`/`float()` crudos sobre
el JSON del modelo (empleados="500+", solapamiento="high", probabilidad="85%")
tumbaban la corrida IA ENTERA o devolvían 500. El resto del código sanea con
`str(...).strip()`; estos puntos hacían lo contrario.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cliente_ia.proveedores import llm as mod_llm  # noqa: E402


# ---------------------------------------------------------------------------
# Coerción tolerante
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("entrada,esperado", [
    ("500+", 500), ("~300", 300), ("1.200", 1200), ("N/A", 0), ("", 0),
    (None, 0), (250, 250), (250.9, 250), ("dos mil", 0), (True, 0), ("0", 0),
])
def test_a_int_no_revienta_nunca(entrada, esperado):
    assert mod_llm._a_int(entrada) == esperado


@pytest.mark.parametrize("entrada,esperado", [
    ("0.8", 0.8), ("high", 0.5), ("", 0.5), (None, 0.5), (0.3, 0.3),
    ("0,72", 0.72), ("80%", 80.0), (1, 1.0), (True, 0.5),
])
def test_a_float_no_revienta_nunca(entrada, esperado):
    assert mod_llm._a_float(entrada, 0.5) == esperado


def test_los_helpers_devuelven_siempre_el_tipo_correcto_sin_excepcion():
    """Nunca una excepción, pase lo que pase — es lo que evita que un solo
    prospecto raro descarte las 60 empresas de la corrida."""
    for basura in ({"raro": 1}, [1, 2], object(), "", "  ", "€€€"):
        assert isinstance(mod_llm._a_int(basura), int)
        assert isinstance(mod_llm._a_float(basura, 0.5), float)


# ---------------------------------------------------------------------------
# Análisis: probabilidad "85%" no da 500
# ---------------------------------------------------------------------------
def test_analisis_probabilidad_como_texto_no_da_500():
    """El modelo devuelve la probabilidad como texto ("85%") y antes eso
    escapaba como ValueError → 500 en /api/analisis. Ahora entra por _a_int."""
    from cliente_ia import analisis

    class _LLMFake:
        def _pedir(self, prompt, tope=10000):
            return ('{"probabilidad_exito":"85%","veredicto":"ok",'
                    '"mercado_potencial":{},"foda":[]}')

    r = analisis.cualitativo(_LLMFake(), {"categoria": "x", "nicho": "y"}, [],
                             idioma="es")
    assert r["probabilidad_exito"] == 85
