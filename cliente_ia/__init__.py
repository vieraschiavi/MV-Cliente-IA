"""
MV Cliente IA · motor AutoGTM
==============================
Réplica del flujo de Explee (auto-GTM) sobre el stack y el diseño de
MV Kobra AI: se le da la URL de un producto y el motor recorre seis fases —
investigar la empresa, explorar la competencia, definir campañas, encontrar
empresas objetivo, encontrar decisores y redactar los correos — priorizando
Uruguay, después LATAM y después el resto del mundo.

El motor es agnóstico del origen de los datos: cada fase le pide lo que
necesita a un `Proveedor` (ver `cliente_ia.proveedores`). Hay tres:

- `ProveedorDemo`  — catálogo sintético determinista. Es el que usan los
  tests y la demo comercial: **no** son empresas ni personas reales.
- `ProveedorWeb`   — lee el sitio real que se le pasa (HTML público) para
  extraer la propuesta de valor, el sector y las señales del ICP.
- `ProveedorLLM`   — usa la API de Claude para la investigación abierta
  (competencia, campañas, listas de empresas objetivo) cuando hay clave.

La convención de datos es la de Kobra: nunca se inventan personas reales.
En modo demo los decisores son personas sintéticas y quedan marcadas como
tales en cada registro (`sintetico=True`) y en la interfaz.
"""

__version__ = "1.1.0"
__all__ = ["__version__"]
