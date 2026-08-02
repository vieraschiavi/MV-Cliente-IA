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
        # Fallos que la cadena absorbió cayendo al siguiente proveedor. El
        # pipeline los copia a `corrida.avisos`: una corrida "con IA" que en
        # silencio terminó en datos sintéticos parece rota — hay que decir
        # qué pasó y en qué fase.
        self.errores: list[str] = []

    def _intentar(self, metodo: str, *args):
        ultimo_error: Exception | None = None
        # "Respondió vacío" y "no respondió nadie" son cosas distintas. Un
        # producto de una categoría sin competidores precargados devuelve []
        # legítimamente, y eso NO es un fallo: tratarlo como tal tumbaba la
        # corrida entera con NotImplementedError en la fase 2 (lo encontró un
        # usuario con un sitio inmobiliario en modo web).
        vacio_valido = None
        alguno_respondio = False
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
                # El mensaje va al usuario: proveedor + fase + motivo, corto.
                self.errores.append(f"{p.nombre} · {metodo}: {str(e)[:300]}")
                continue
            alguno_respondio = True
            if r:
                return r
            vacio_valido = r                            # se sigue por si otro trae más
        if alguno_respondio:
            return vacio_valido
        if ultimo_error is not None:
            raise ultimo_error
        raise NotImplementedError(f"Ningún proveedor resolvió {metodo}")

    def investigar(self, dominio):
        return self._intentar("investigar", dominio)

    def perfilar(self, empresa):
        """Afina el perfil de la fase 1 (nicho, sectores, dolores) con el
        texto real del sitio. Sólo el proveedor LLM la implementa; sin IA
        la cadena levanta NotImplementedError y el pipeline sigue con el
        perfil del catálogo."""
        return self._intentar("perfilar", empresa)

    def competencia(self, empresa):
        return self._intentar("competencia", empresa)

    def campanas(self, empresa, competidores):
        return self._intentar("campanas", empresa, competidores)

    def prospectos(self, empresa, campanas, limite):
        return self._intentar("prospectos", empresa, campanas, limite)

    def decisores(self, prospectos, por_empresa):
        return self._intentar("decisores", prospectos, por_empresa)
