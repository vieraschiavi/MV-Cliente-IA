"""
MV Cliente IA · interfaz de proveedor
======================================
Cada fase del pipeline le pide al proveedor exactamente lo que necesita.
Cambiar de proveedor (demo / web / LLM) no cambia una línea de las fases ni
del scoring: sólo cambia de dónde salen los datos.

Un proveedor puede implementar sólo una parte y delegar el resto — es lo que
hace `ProveedorWeb`, que sabe leer un sitio real pero no inventa prospectos,
y por eso encadena con el demo para las fases que no cubre.
"""
from __future__ import annotations

from ..modelos import Campana, Competidor, Decisor, Empresa, Prospecto


class Proveedor:
    """Contrato de las seis fases. El nombre viaja en cada registro (`fuente`)."""

    nombre = "base"

    # --- Fase 1 -----------------------------------------------------------
    def investigar(self, dominio: str) -> Empresa:
        raise NotImplementedError

    # --- Fase 2 -----------------------------------------------------------
    def competencia(self, empresa: Empresa) -> list[Competidor]:
        raise NotImplementedError

    # --- Fase 3 -----------------------------------------------------------
    def campanas(self, empresa: Empresa, competidores: list[Competidor]) -> list[Campana]:
        raise NotImplementedError

    # --- Fase 4 -----------------------------------------------------------
    def prospectos(self, empresa: Empresa, campanas: list[Campana],
                   limite: int) -> list[Prospecto]:
        raise NotImplementedError

    # --- Fase 5 -----------------------------------------------------------
    def decisores(self, prospectos: list[Prospecto],
                  por_empresa: int) -> list[Decisor]:
        raise NotImplementedError


class ProveedorEncadenado(Proveedor):
    """
    Usa el primer proveedor que sepa responder cada fase y cae al siguiente
    si falla o devuelve vacío. Así `ProveedorWeb` aporta la investigación real
    del sitio y el demo completa el resto sin que las fases se enteren.
    """

    def __init__(self, *proveedores: Proveedor):
        if not proveedores:
            raise ValueError("Hace falta al menos un proveedor")
        self.proveedores = proveedores
        self.nombre = "+".join(p.nombre for p in proveedores)

    def _intentar(self, metodo: str, *args):
        ultimo_error: Exception | None = None
        for p in self.proveedores:
            fn = getattr(p, metodo, None)
            if fn is None:
                continue
            try:
                r = fn(*args)
            except NotImplementedError:
                continue
            except Exception as e:                      # noqa: BLE001
                ultimo_error = e                        # se prueba el siguiente
                continue
            if r:
                return r
        if ultimo_error is not None:
            raise ultimo_error
        raise NotImplementedError(f"Ningún proveedor resolvió {metodo}")

    def investigar(self, dominio):
        return self._intentar("investigar", dominio)

    def competencia(self, empresa):
        return self._intentar("competencia", empresa)

    def campanas(self, empresa, competidores):
        return self._intentar("campanas", empresa, competidores)

    def prospectos(self, empresa, campanas, limite):
        return self._intentar("prospectos", empresa, campanas, limite)

    def decisores(self, prospectos, por_empresa):
        return self._intentar("decisores", prospectos, por_empresa)
