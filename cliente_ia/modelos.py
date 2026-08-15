"""
MV Cliente IA · modelos de dominio
===================================
Las estructuras que viajan entre las fases del pipeline y salen por la API.
Todas serializan a dict plano (`a_dict`) porque el backend las devuelve como
JSON y la app las guarda en disco tal cual (`cliente_ia.almacen`).

Nota de honestidad: `sintetico` viaja en cada `Decisor` y cada `Prospecto`.
Cuando corre el proveedor demo vale True y la interfaz lo muestra con un
cartel — igual que el banner de datos de demo de MV Kobra AI.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields

from . import geo

# Las seis fases del flujo, en orden. Los nombres de los pasos son los mismos
# que muestra la interfaz (ver webapp/frontend/src/i18n/*.json).
FASES = (
    "investigar",     # 1 · Investigá tu empresa
    "competencia",    # 2 · Explorá la competencia
    "campanas",       # 3 · Definí campañas
    "prospectos",     # 4 · Encontrá clientes potenciales
    "decisores",      # 5 · Encontrá a los decisores
    "emails",         # 6 · Escribí los correos
)

ESTADOS = ("pendiente", "corriendo", "listo", "error")


@dataclass
class Empresa:
    """Fase 1 — lo que sabemos del producto que sale a vender."""
    dominio: str
    nombre: str = ""
    propuesta: str = ""                       # una frase: qué hace y para quién
    categoria: str = ""                       # cómo se llama la categoría de producto
    pais: str = "UY"                          # mercado base
    idiomas: list[str] = field(default_factory=lambda: list(geo.IDIOMAS))
    sectores_objetivo: list[str] = field(default_factory=list)
    dolores: list[str] = field(default_factory=list)
    diferenciales: list[str] = field(default_factory=list)
    tamano_objetivo: str = ""                 # ej. "50-5000 empleados"
    # Texto crudo extraído de la web real (título + descripción + cuerpo).
    # Es lo que le damos al LLM para que razone sobre el producto VERDADERO:
    # sin esto usaba la categoría del catálogo demo y traía competidores y
    # prospectos de cualquier rubro menos el del sitio.
    resumen_sitio: str = ""
    fuente: str = "demo"                      # "web" | "llm" | "demo"
    # Los mismos textos en los tres idiomas del producto:
    #   {"es": {"propuesta": str, "dolores": [str], "diferenciales": [str]}, ...}
    # La fase 6 le escribe a cada decisor en el idioma de su país, así que
    # necesita la propuesta y el diferencial en ese idioma — no alcanza con
    # los campos planos de arriba, que están en el idioma de la interfaz.
    textos: dict[str, dict] = field(default_factory=dict)

    def texto(self, idioma: str, clave: str, defecto=None):
        """Un texto en el idioma pedido, con caída al campo plano."""
        valor = (self.textos.get(idioma) or {}).get(clave)
        if valor:
            return valor
        return getattr(self, clave, defecto) if defecto is None else defecto

    def a_dict(self) -> dict:
        return asdict(self)


@dataclass
class Competidor:
    dominio: str
    nombre: str = ""
    posicionamiento: str = ""
    pais: str = ""
    solapamiento: float = 0.0                 # 0..1 · cuánto pisa nuestro ICP
    fuente: str = "demo"

    def a_dict(self) -> dict:
        return asdict(self)


@dataclass
class Campana:
    """Fase 3 — un segmento con su ángulo de mensaje y su ola geográfica."""
    id: str
    nombre: str
    sector: str
    nivel: str                                # "local" | "latam" | "mundo"
    prioridad: int                            # 1 · 2 · 3 (ver geo)
    paises: list[str] = field(default_factory=list)
    angulo: str = ""                          # el gancho del mensaje
    dolor: str = ""
    prueba: str = ""                          # la prueba/dato que respalda el ángulo
    idioma: str = "es"

    def a_dict(self) -> dict:
        return asdict(self)


@dataclass
class Prospecto:
    """Fase 4 — una empresa objetivo."""
    id: str
    nombre: str
    dominio: str
    sector: str
    pais: str
    ciudad: str = ""
    empleados: int = 0
    descripcion: str = ""
    senales: list[str] = field(default_factory=list)   # por qué ahora
    # Dolor del sector YA en el idioma de este prospecto. La campaña lo tiene
    # en el idioma de su ola, que no siempre coincide (Brasil está en la ola
    # LATAM, que trabaja en español, pero se le escribe en portugués).
    dolor: str = ""
    campana_id: str = ""
    score: float = 0.0                        # 0..100 (ver scoring)
    ajuste_icp: float = 0.0                   # 0..1 antes del peso geográfico
    prioridad: int = 3
    nivel: str = "mundo"
    idioma: str = "es"
    sintetico: bool = True
    fuente: str = "demo"
    # Contactos PÚBLICOS leídos del propio sitio de la empresa (sólo reales):
    # {email, emails, telefono, linkedin, instagram, web}. Lo que la empresa
    # no publica, no está — acá no se adivina nada.
    contactos: dict = field(default_factory=dict)

    def a_dict(self) -> dict:
        return asdict(self)


@dataclass
class Decisor:
    """Fase 5 — la persona a la que se le escribe."""
    id: str
    prospecto_id: str
    nombre: str
    cargo: str
    empresa: str
    pais: str
    email: str = ""
    linkedin: str = ""
    seniority: str = ""                       # "c-level" | "director" | "gerente"
    idioma: str = "es"
    score: float = 0.0
    sintetico: bool = True
    fuente: str = "demo"

    def a_dict(self) -> dict:
        return asdict(self)


@dataclass
class Email:
    """
    Fase 6 — el mensaje listo para enviar, en las cuatro formas en que se
    manda: correo en texto plano, correo HTML (con banner y video), mensaje
    de LinkedIn y nota de invitación de LinkedIn.

    Las tres piezas que no son texto —banner, video y enlace a la web— van
    **en el idioma del país del receptor**, igual que el texto (ver
    `cliente_ia.enlaces`).
    """
    id: str
    decisor_id: str
    prospecto_id: str
    para: str
    idioma: str
    asunto: str
    cuerpo: str
    seguimiento: str = ""                     # el segundo toque, +3 días
    cuerpo_html: str = ""                     # versión HTML con banner y CTA
    linkedin: str = ""                        # mensaje directo / InMail
    linkedin_nota: str = ""                   # nota de invitación (≤300 car.)
    landing_url: str = ""
    video_url: str = ""                       # vacío = no hay video que ofrecer
    banner_url: str = ""
    campana_id: str = ""
    palabras: int = 0

    def a_dict(self) -> dict:
        return asdict(self)


@dataclass
class PasoFase:
    """Estado de una fase dentro de una corrida — es lo que pinta el acordeón."""
    clave: str
    estado: str = "pendiente"
    detalle: str = ""
    items: int = 0
    ms: int = 0

    def a_dict(self) -> dict:
        return asdict(self)


@dataclass
class Corrida:
    """Una corrida completa del AutoGTM sobre un dominio."""
    id: str
    dominio: str
    creada: str = ""
    estado: str = "pendiente"
    modo: str = "demo"                        # "demo" | "web" | "llm"
    # Recorte geográfico elegido: "todos" (el país base primero, en
    # proporción), "local" (sólo ese país), "regional" (su región) o "mundo".
    mercado: str = "todos"
    # País propio del cliente: el que ocupa la ola local. Es lo que hace que
    # las olas sean relativas y no "Uruguay y después los demás".
    pais_base: str = "UY"
    idioma_ui: str = "es"
    # Configuración de enlaces (sitio, video y banner por idioma) tal como se
    # usó en esta corrida — se guarda para que reabrir una corrida vieja
    # muestre los mismos mensajes que se mandaron.
    enlaces: dict = field(default_factory=dict)
    pasos: list[PasoFase] = field(default_factory=list)
    empresa: Empresa | None = None
    competidores: list[Competidor] = field(default_factory=list)
    campanas: list[Campana] = field(default_factory=list)
    prospectos: list[Prospecto] = field(default_factory=list)
    decisores: list[Decisor] = field(default_factory=list)
    emails: list[Email] = field(default_factory=list)
    error: str = ""
    # Qué falló POR DENTRO sin tumbar la corrida: cuando un proveedor de la
    # cadena (p. ej. el LLM) se cae y otro lo cubre, acá queda el motivo. La
    # interfaz lo muestra — una corrida "con IA" que en realidad usó datos
    # sintéticos sin decir por qué ya confundió a un usuario.
    avisos: list[str] = field(default_factory=list)

    def paso(self, clave: str) -> PasoFase:
        for p in self.pasos:
            if p.clave == clave:
                return p
        p = PasoFase(clave)
        self.pasos.append(p)
        return p

    def a_dict(self) -> dict:
        return {
            "id": self.id,
            "dominio": self.dominio,
            "creada": self.creada,
            "estado": self.estado,
            "modo": self.modo,
            "mercado": self.mercado,
            "pais_base": self.pais_base,
            "pais_base_nombre": geo.nombre_pais(self.pais_base, self.idioma_ui),
            "region_base": geo.nombre_region(geo.region_de(self.pais_base),
                                             self.idioma_ui),
            "idioma_ui": self.idioma_ui,
            "enlaces": dict(self.enlaces),
            "error": self.error,
            "avisos": list(self.avisos),
            "pasos": [p.a_dict() for p in self.pasos],
            "empresa": self.empresa.a_dict() if self.empresa else None,
            "competidores": [c.a_dict() for c in self.competidores],
            "campanas": [c.a_dict() for c in self.campanas],
            "prospectos": [p.a_dict() for p in self.prospectos],
            "decisores": [d.a_dict() for d in self.decisores],
            "emails": [e.a_dict() for e in self.emails],
            "resumen": self.resumen(),
        }

    def resumen(self) -> dict:
        """Los números de cabecera: cuántos prospectos por ola geográfica."""
        por_nivel = dict.fromkeys(geo.NIVELES, 0)
        for p in self.prospectos:
            por_nivel[geo.normalizar_nivel(p.nivel)] += 1
        por_idioma: dict[str, int] = {}
        for e in self.emails:
            por_idioma[e.idioma] = por_idioma.get(e.idioma, 0) + 1
        return {
            "con_video": sum(1 for e in self.emails if e.video_url),
            "con_linkedin": sum(1 for e in self.emails if e.linkedin),
            "competidores": len(self.competidores),
            "campanas": len(self.campanas),
            "prospectos": len(self.prospectos),
            "decisores": len(self.decisores),
            "emails": len(self.emails),
            "prospectos_por_nivel": por_nivel,
            "emails_por_idioma": por_idioma,
        }


def _solo(cls, d: dict) -> dict:
    """Filtra `d` a los campos que `cls` conoce. Sin esto, una corrida
    guardada por una versión previa que traiga una clave renombrada o quitada
    tumbaba la reconstrucción con TypeError —y como `almacen.cargar` sólo
    reintenta PermissionError, subía como 500 al abrir o exportar esa corrida
    vieja—. Una clave que ya no existe se ignora; una nueva que falta usa el
    default del dataclass."""
    validos = {f.name for f in fields(cls)}
    return {k: v for k, v in (d or {}).items() if k in validos}


def desde_dict(d: dict) -> Corrida:
    """Reconstruye una corrida guardada en disco. Tolera deriva de esquema
    entre versiones: campos desconocidos se ignoran (ver `_solo`)."""
    c = Corrida(
        id=d["id"], dominio=d["dominio"], creada=d.get("creada", ""),
        estado=d.get("estado", "pendiente"), modo=d.get("modo", "demo"),
        mercado=geo.normalizar_nivel(d["mercado"]) if d.get("mercado") not in
        (None, "", "todos") else "todos",
        pais_base=d.get("pais_base") or (d.get("empresa") or {}).get("pais") or "UY",
        idioma_ui=d.get("idioma_ui", "es"), error=d.get("error", ""),
        enlaces=d.get("enlaces") or {},
    )
    c.avisos = [str(a) for a in d.get("avisos", [])]
    c.pasos = [PasoFase(**_solo(PasoFase, p)) for p in d.get("pasos", [])]
    if d.get("empresa"):
        c.empresa = Empresa(**_solo(Empresa, d["empresa"]))
    c.competidores = [Competidor(**_solo(Competidor, x)) for x in d.get("competidores", [])]
    c.campanas = [Campana(**_solo(Campana, x)) for x in d.get("campanas", [])]
    c.prospectos = [Prospecto(**_solo(Prospecto, x)) for x in d.get("prospectos", [])]
    # Las corridas guardadas antes de que el país base fuera elegible traen la
    # ola regional escrita "latam". Se traduce al abrirlas para que el filtro
    # de la tabla y el resumen sigan encontrándolas.
    for fila in (*c.campanas, *c.prospectos):
        fila.nivel = geo.normalizar_nivel(fila.nivel)
    c.decisores = [Decisor(**_solo(Decisor, x)) for x in d.get("decisores", [])]
    c.emails = [Email(**_solo(Email, x)) for x in d.get("emails", [])]
    return c
