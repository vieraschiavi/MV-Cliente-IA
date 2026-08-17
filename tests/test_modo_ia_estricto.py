"""
El modo IA es estricto y el filtro de mercado alcanza a la competencia.

Los dos vienen de la misma corrida real, hecha desde la app de PC con
«Investigación con IA» y mercado «Sólo Uruguay»: la llamada a Claude murió
por timeout, la cadena tapó el hueco con datos demo EN SILENCIO, y encima
la competencia mostrada era de Brasil y EE.UU. porque el recorte de mercado
se aplicaba a campañas y prospectos pero nunca a los competidores. El
usuario pidió IA de su país y recibió sintético de cualquier lado.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cliente_ia import pipeline  # noqa: E402
from cliente_ia.modelos import Competidor  # noqa: E402
from cliente_ia.proveedores import ProveedorDemo, ProveedorEncadenado  # noqa: E402
from cliente_ia.proveedores import llm as mod_llm  # noqa: E402


# ---------------------------------------------------------------------------
# La cadena con proveedor decisivo
# ---------------------------------------------------------------------------
class _IAQueFalla:
    nombre = "ia"

    def competencia(self, empresa):
        raise RuntimeError("No se pudo llamar a claude: TimeoutError")


class _IAQueDiceNoHay:
    nombre = "ia"

    def competencia(self, empresa):
        return []


def _empresa():
    return ProveedorDemo().investigar("mvkobranzaia.com")


def test_si_la_ia_falla_no_se_rellena_con_demo():
    """Lo que vio el usuario: pidió IA, la IA falló, y la corrida siguió
    como si nada con seis competidores sintéticos. Con la IA como proveedor
    decisivo, su fallo ES el fallo de la fase — sin red de datos demo."""
    ia = _IAQueFalla()
    cadena = ProveedorEncadenado(ia, ProveedorDemo(), decisivo=ia)
    with pytest.raises(RuntimeError, match="TimeoutError"):
        cadena.competencia(_empresa())
    # Y el motivo queda anotado para los avisos de la corrida.
    assert any("TimeoutError" in e for e in cadena.errores)


def test_si_la_ia_dice_no_hay_el_demo_no_lo_contradice():
    """[] de la IA es una respuesta («ningún competidor con base acá»), no
    un hueco que el demo deba llenar con empresas de otros países."""
    ia = _IAQueDiceNoHay()
    cadena = ProveedorEncadenado(ia, ProveedorDemo(), decisivo=ia)
    assert cadena.competencia(_empresa()) == []


def test_lo_que_la_ia_no_hace_a_proposito_sigue_cayendo_al_demo():
    """Regla 6: el LLM nunca propone personas. `decisores` no está en el
    proveedor de IA y tiene que seguir saliendo del demo, marcado sintético,
    aunque la IA sea decisiva."""
    ia = _IAQueDiceNoHay()                     # no implementa decisores
    demo = ProveedorDemo()
    cadena = ProveedorEncadenado(ia, demo, decisivo=ia)
    prospectos = demo.prospectos(_empresa(), demo.campanas(_empresa(), []), 10)
    decisores = cadena.decisores(prospectos, 3)
    assert decisores and all(d.sintetico for d in decisores)


def test_sin_proveedor_decisivo_la_cadena_sigue_cayendo_como_siempre():
    """El modo web depende de caer al demo en lo que no cubre: esa conducta
    no cambia cuando nadie es decisivo."""
    cadena = ProveedorEncadenado(_IAQueFalla(), ProveedorDemo())
    assert cadena.competencia(_empresa())      # el demo respondió


# ---------------------------------------------------------------------------
# El reintento por timeout
# ---------------------------------------------------------------------------
def test_un_timeout_se_reintenta_una_vez(monkeypatch):
    p = mod_llm.ProveedorLLM.__new__(mod_llm.ProveedorLLM)
    p.proveedor = "claude"
    p.notas = []
    p._limite = None                                     # sin presupuesto (no serverless)
    intentos = []

    def una_vez(prompt, max_tokens=8000):
        intentos.append(1)
        if len(intentos) == 1:
            raise mod_llm.ErrorLLM("No se pudo llamar a claude: TimeoutError") \
                from TimeoutError("timed out")
        return '{"ok": true}'

    monkeypatch.setattr(p, "_pedir_una_vez", una_vez)
    assert p._pedir("hola") == '{"ok": true}'
    assert len(intentos) == 2
    assert any("reintent" in n for n in p.notas)


def test_un_error_de_clave_no_se_reintenta(monkeypatch):
    """Repetir un 401 duplica la espera para nada."""
    p = mod_llm.ProveedorLLM.__new__(mod_llm.ProveedorLLM)
    p.proveedor = "claude"
    p.notas = []
    p._limite = None                                     # sin presupuesto (no serverless)
    intentos = []

    def una_vez(prompt, max_tokens=8000):
        intentos.append(1)
        raise mod_llm.ErrorLLM("claude respondió 401: clave inválida")

    monkeypatch.setattr(p, "_pedir_una_vez", una_vez)
    with pytest.raises(mod_llm.ErrorLLM):
        p._pedir("hola")
    assert len(intentos) == 1


def test_detecta_timeouts_de_todas_las_formas():
    """urllib envuelve, el SDK de anthropic usa sus propios tipos (que no
    heredan de TimeoutError) y _post_json deja la causa encadenada."""
    import urllib.error

    class APITimeoutError(Exception):          # como el del SDK: sólo el nombre
        pass

    assert mod_llm._es_timeout(TimeoutError())
    assert mod_llm._es_timeout(APITimeoutError())
    assert mod_llm._es_timeout(urllib.error.URLError(TimeoutError("timed out")))
    encadenado = mod_llm.ErrorLLM("no se pudo")
    encadenado.__cause__ = TimeoutError("timed out")
    assert mod_llm._es_timeout(encadenado)
    assert not mod_llm._es_timeout(mod_llm.ErrorLLM("claude respondió 401"))
    assert not mod_llm._es_timeout(None)


# ---------------------------------------------------------------------------
# El filtro de mercado sobre la competencia
# ---------------------------------------------------------------------------
class _DemoConCompetenciaMundial(ProveedorDemo):
    """Reproduce la pantalla del bug: mercado «sólo Uruguay» y competidores
    de Brasil y EE.UU."""

    def competencia(self, empresa):
        return [
            Competidor(dominio="monest.com.br", nombre="Monest", pais="BR"),
            Competidor(dominio="collectwise.com", nombre="CollectWise", pais="US"),
            Competidor(dominio="cobrar.uy", nombre="CobrarUY", pais="UY"),
        ]


def test_el_filtro_de_mercado_recorta_la_competencia(monkeypatch):
    monkeypatch.setattr(pipeline.proveedores, "construir",
                        lambda *a, **k: _DemoConCompetenciaMundial())
    corrida = pipeline.ejecutar("mvkobranzaia.com", modo="demo",
                                mercado="local", pais_base="UY",
                                limite_prospectos=10)
    assert corrida.estado == "listo"
    assert [c.pais for c in corrida.competidores] == ["UY"], \
        "con «sólo Uruguay» no pueden quedar competidores de BR/US"


def test_si_el_recorte_no_deja_competidores_se_avisa(monkeypatch):
    """Cero competidores sin explicación parece una fase rota: se muestran
    todos y el aviso dice por qué, igual que hace el filtro de campañas."""
    monkeypatch.setattr(pipeline.proveedores, "construir",
                        lambda *a, **k: _DemoConCompetenciaMundial())
    corrida = pipeline.ejecutar("mvkobranzaia.com", modo="demo",
                                mercado="local", pais_base="JP",
                                limite_prospectos=10)
    assert corrida.estado == "listo"
    assert len(corrida.competidores) == 3
    assert any("competidor" in a.lower() and "Japón" in a for a in corrida.avisos)
