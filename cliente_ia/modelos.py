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
    # Afinidad MEDIDA: se bajó la web del competidor y se comparó contra la
    # huella del producto (cliente_ia/segmento.py). `solapamiento` lo DECLARA
    # el modelo; esto lo comprueba el motor. -1 = no se pudo verificar (sitio
    # caído, sin red). Los dos conviven a propósito: cuando no coinciden, el
    # que manda para filtrar es este.
    afinidad: float = -1.0
    # Si este competidor le vende DE VERDAD a clientes del mercado elegido,
    # aunque tenga su base en otro país. Lo declara el modelo en la fase 2.
    #
    # Existe porque el dato se estaba perdiendo entre el proveedor y el
    # pipeline: el proveedor de IA ya se quedaba con «los de casa MÁS los de
    # afuera que venden acá», y después el pipeline volvía a filtrar por país
    # de BASE y los tiraba igual. Con «sólo Uruguay», dos competidores
    # regionales que sí le sacan clientes a un uruguayo desaparecían, y el
    # programa decía «ningún competidor tiene base en el mercado elegido; se
    # muestran los de todos lados» — mostrando justamente a los que no le
    # compiten ahí.
    #
    # Default False a propósito: el proveedor demo no lo declara, así que su
    # recorte por país sigue siendo exactamente el de antes.
    vende_en_objetivo: bool = False
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
    # Afinidad medida del sitio del prospecto contra la huella del producto.
    # Sale GRATIS: se calcula con el mismo HTML que se baja para los
    # contactos públicos, sin un pedido extra. -1 = no verificado.
    afinidad: float = -1.0
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
    # El formulario de pedido de demo (`landing#demo`): es el destino del
    # botón, porque el programa instalado ya no se descarga de la web.
    demo_url: str = ""
    captura_url: str = ""                     # segunda imagen: el producto real
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


# Las tres clases de aviso. La distinción NO es cosmética: la interfaz las
# muestra bajo carteles distintos, y meterlas en la misma bolsa hacía que el
# programa se acusara solo de haber fallado cuando no había fallado nada.
AVISO_FALLO = "fallo"     # algo se cayó y lo cubrió otra cosa (datos sintéticos)
AVISO_AJUSTE = "ajuste"   # el resultado se acomodó y conviene saberlo
AVISO_DATO = "dato"       # lo que se verificó: un resultado, y de los buenos


class Aviso(str):
    """Un aviso de la corrida, con de qué CLASE es.

    Es un `str` a todos los efectos —se compara, se busca con `in`, se
    serializa y se loguea como el texto pelado— así que el código que lo
    trataba como texto sigue igual. Lo que agrega es `.tipo`.

    Por qué hizo falta: los avisos eran una sola lista de strings y la interfaz
    los mostraba TODOS abajo de un cartel que decía «algunas fases con IA
    fallaron y se cubrieron con datos sintéticos». Ahí adentro caían cosas que
    no eran ni un fallo ni datos sintéticos: que ningún competidor tuviera base
    en el mercado elegido (una nota del filtro), y hasta resultados buenos como
    «Contactos públicos: 23 de 50 empresas reales publican correo». El programa
    terminaba diciendo que había fallado y que los datos eran sintéticos justo
    arriba de datos REALES que había verificado él mismo. Eso rompe la regla
    del proyecto en los dos sentidos: lo sintético se dice sintético, y lo real
    no se declara falso.
    """

    __slots__ = ("tipo",)

    def __new__(cls, texto: str, tipo: str = AVISO_AJUSTE) -> Aviso:
        obj = super().__new__(cls, texto)
        obj.tipo = tipo if tipo in (AVISO_FALLO, AVISO_AJUSTE, AVISO_DATO) \
            else AVISO_AJUSTE
        return obj

    def a_dict(self) -> dict:
        return {"m": str(self), "t": self.tipo}


def _aviso_desde(x) -> Aviso:
    """Acepta lo nuevo y lo viejo.

    Las corridas guardadas antes de que los avisos tuvieran clase son strings
    pelados. Se leen como `ajuste`: es el tipo neutro — no acusa a esa corrida
    vieja de haber fallado ni le atribuye un resultado verificado.
    """
    # Un `Aviso` ya clasificado se devuelve tal cual. La comprobación va
    # PRIMERO y no se puede sacar: `Aviso` es un `str`, así que sin esto caía
    # en la rama del texto pelado de abajo y perdía su tipo — todo terminaba
    # como `ajuste` al guardar. Lo encontró la prueba de ida y vuelta, no la
    # lectura del código.
    if isinstance(x, Aviso):
        return x
    if isinstance(x, dict):
        return Aviso(str(x.get("m", "")), str(x.get("t", AVISO_AJUSTE)))
    return Aviso(str(x), AVISO_AJUSTE)


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
    # Lo que hay que contarle al usuario de esta corrida, CADA COSA CON SU
    # CLASE (ver `Aviso`). La interfaz lo muestra — una corrida "con IA" que en
    # realidad usó datos sintéticos sin decir por qué ya confundió a un
    # usuario, y meter todo en la misma bolsa confundió a otro (ver `Aviso`).
    avisos: list[Aviso] = field(default_factory=list)
    # Las palabras que MIDEN el segmento del producto, contadas sobre su propia
    # web (cliente_ia/segmento.py). Se guardan para que la interfaz pueda
    # mostrar con qué criterio se filtró — un filtro que no dice qué usó es
    # indistinguible de un capricho.
    palabras_segmento: list[str] = field(default_factory=list)
    # Consultas listas para encontrar MÁS clientes de cada segmento en las
    # redes (cliente_ia/busqueda_social.py): [{campana_id, sector, nivel,
    # pais, busquedas: [{red, etiqueta, consulta, url}]}].
    busquedas: list[dict] = field(default_factory=list)

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
            # Como dicts {m, t}: la interfaz necesita la CLASE de cada uno para
            # no mostrar un resultado verificado abajo del cartel de fallos.
            "avisos": [_aviso_desde(a).a_dict() for a in self.avisos],
            "palabras_segmento": list(self.palabras_segmento),
            "busquedas": list(self.busquedas),
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
    c.avisos = [_aviso_desde(a) for a in d.get("avisos", [])]
    c.palabras_segmento = [str(x) for x in d.get("palabras_segmento", [])]
    c.busquedas = [x for x in d.get("busquedas", []) if isinstance(x, dict)]
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
