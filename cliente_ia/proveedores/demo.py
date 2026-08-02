"""
MV Cliente IA · proveedor demo (datos sintéticos deterministas)
===============================================================
Es el proveedor por defecto: no necesita clave de API ni salida a internet,
corre igual en la notebook, en el instalador de Windows y en el APK, y da
**siempre el mismo resultado para el mismo dominio** (la semilla sale del
dominio), que es lo que permite testearlo.

Convención heredada de MV Kobra AI: los datos son sintéticos y se dicen
sintéticos. Los sectores, los cargos y las ciudades son taxonomía pública
real; los nombres de empresa y las personas se componen acá y viajan con
`sintetico=True` para que la interfaz lo muestre. Cualquier parecido con una
organización o una persona real es casualidad de la combinatoria.
"""
from __future__ import annotations

import json
import random
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from .. import geo
from ..modelos import Campana, Competidor, Decisor, Empresa, Prospecto
from .base import Proveedor

RUTA_SEMILLA = Path(__file__).resolve().parent.parent / "datos" / "mercado.json"

# Palabras del dominio/sitio que delatan la categoría de producto. Se prueban
# en orden; la primera que pega manda.
PISTAS_CATEGORIA = {
    "cobranzas": ("kobra", "cobranz", "cobranca", "cobrança", "collect", "recupero",
                  "recovery", "debt", "morosid", "delinquen", "receivable", "inadimpl"),
}
CATEGORIA_DEFAULT = "saas_generico"

# Cuántos sectores entran en cada ola. Uruguay se trabaja a fondo; afuera se
# entra por los sectores donde el producto ya tiene caso.
SECTORES_POR_NIVEL = {"local": 6, "latam": 4, "mundo": 3}


@lru_cache(maxsize=1)
def semilla() -> dict:
    with open(RUTA_SEMILLA, encoding="utf-8") as f:
        return json.load(f)


def _slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def _semilla_de(dominio: str) -> int:
    """Semilla estable a partir del dominio (hash() de Python no lo es entre corridas)."""
    return int.from_bytes(_slug(dominio).encode()[:8].ljust(8, b"\0"), "big") % (2**31)


def _texto(valor, idioma: str = "es"):
    """Los campos multi-idioma de la semilla son dict; los simples, str."""
    if isinstance(valor, dict):
        return valor.get(idioma) or valor.get("es") or next(iter(valor.values()))
    return valor


def _repartir(total: int, pesos: list[float]) -> list[int]:
    """
    Reparte `total` entre `pesos` sin perder unidades por redondeo (método del
    resto mayor). Redondear cada tajada por separado dejaba en cero a todos los
    mercados chicos y la corrida terminaba con menos prospectos de los pedidos.
    """
    suma = sum(pesos)
    if total <= 0 or suma <= 0:
        return [0] * len(pesos)
    exactos = [total * p / suma for p in pesos]
    base = [int(x) for x in exactos]
    faltan = total - sum(base)
    # Las unidades sueltas van a las tajadas con mayor resto; a igualdad de
    # resto, al mercado más denso (que viene primero en la lista de la ola).
    orden = sorted(range(len(pesos)), key=lambda i: (-(exactos[i] - base[i]), -pesos[i], i))
    for i in orden[:faltan]:
        base[i] += 1
    return base


class ProveedorDemo(Proveedor):
    nombre = "demo"

    def __init__(self, idioma_base: str = "es"):
        self.idioma_base = idioma_base if idioma_base in geo.IDIOMAS else "es"
        self.datos = semilla()

    # ------------------------------------------------------------------
    # Fase 1 · investigar la empresa
    # ------------------------------------------------------------------
    def detectar_categoria(self, texto: str) -> str:
        t = _slug(texto)
        for categoria, pistas in PISTAS_CATEGORIA.items():
            if any(_slug(p) in t for p in pistas):
                return categoria
        return CATEGORIA_DEFAULT

    # La propuesta de valor por categoría, en los tres idiomas del producto.
    # No lleva el nombre de la empresa adentro: lo antepone la plantilla del
    # correo, y tenerlo en los dos lados lo escribía duplicado.
    PROPUESTAS = {
        "cobranzas": {
            "es": "predice qué deudores van a pagar, prioriza la cartera por valor esperado "
                  "de recupero y negocia por voz y WhatsApp, con control de calidad de cada gestión",
            "pt": "prevê quais devedores vão pagar, prioriza a carteira por valor esperado de "
                  "recuperação e negocia por voz e WhatsApp, com controle de qualidade de cada contato",
            "en": "predicts which debtors will pay, orders the book by expected recovery value "
                  "and negotiates over voice and WhatsApp, with quality control on every interaction",
        },
        "saas_generico": {
            "es": "resuelve un problema operativo concreto de equipos B2B con software que se "
                  "implementa en días",
            "pt": "resolve um problema operacional concreto de equipes B2B com software que se "
                  "implanta em dias",
            "en": "solves one concrete operational problem for B2B teams with software that "
                  "deploys in days",
        },
    }

    def _textos_multi(self, categoria: str, icp: dict, sectores: dict) -> dict[str, dict]:
        """Propuesta, dolores y diferenciales en es/pt/en (los usa la fase 6)."""
        salida: dict[str, dict] = {}
        for idioma in geo.IDIOMAS:
            salida[idioma] = {
                "propuesta": self.PROPUESTAS[categoria][idioma],
                "dolores": [_texto(sectores[c]["dolores"], idioma)[0]
                            for c in icp["sectores"][:4]],
                "diferenciales": list(_texto(icp["diferenciales"], idioma)),
            }
        return salida

    def investigar(self, dominio: str) -> Empresa:
        idioma = self.idioma_base
        categoria = self.detectar_categoria(dominio)
        icp = self.datos["icp_por_categoria"][categoria]
        sectores = self.datos["sectores"]

        pais = geo.pais_de_dominio(dominio) or geo.PAIS_DEFAULT
        nombre = re.sub(r"\.(com|net|org|ai|io|co)(\.[a-z]{2})?$", "", dominio, flags=re.I)
        nombre = nombre.replace("www.", "").split(".")[0].replace("-", " ").title()

        textos = self._textos_multi(categoria, icp, sectores)
        return Empresa(
            dominio=dominio,
            nombre=nombre,
            propuesta=f"{nombre} {textos[idioma]['propuesta']}.",
            categoria=_texto(icp["categoria"], idioma),
            pais=pais.codigo,
            idiomas=list(geo.IDIOMAS),
            sectores_objetivo=[_texto(sectores[s]["nombre"], idioma) for s in icp["sectores"]],
            dolores=list(textos[idioma]["dolores"]),
            diferenciales=list(textos[idioma]["diferenciales"]),
            tamano_objetivo=icp["tamano_objetivo"],
            fuente=self.nombre,
            textos=textos,
        )

    # ------------------------------------------------------------------
    # Fase 2 · explorar la competencia
    # ------------------------------------------------------------------
    def competencia(self, empresa: Empresa) -> list[Competidor]:
        categoria = self.detectar_categoria(empresa.dominio + " " + empresa.categoria)
        icp = self.datos["icp_por_categoria"][categoria]
        salida = [
            Competidor(
                dominio=c["dominio"],
                nombre=c["nombre"],
                posicionamiento=_texto(c["posicionamiento"], self.idioma_base),
                pais=c.get("pais", ""),
                solapamiento=c.get("solapamiento", 0.0),
                fuente=self.nombre,
            )
            for c in icp.get("competidores", [])
        ]
        return sorted(salida, key=lambda c: -c.solapamiento)

    # ------------------------------------------------------------------
    # Fase 3 · definir campañas
    # ------------------------------------------------------------------
    def _claves_sector(self, empresa: Empresa) -> list[str]:
        categoria = self.detectar_categoria(empresa.dominio + " " + empresa.categoria)
        return list(self.datos["icp_por_categoria"][categoria]["sectores"])

    def campanas(self, empresa: Empresa, competidores: list[Competidor]) -> list[Campana]:
        sectores = self.datos["sectores"]
        claves = self._claves_sector(empresa)
        prueba_base = (empresa.diferenciales or [""])[0]

        salida: list[Campana] = []
        for nivel, prioridad, codigos in geo.orden_de_olas():
            cuantos = SECTORES_POR_NIVEL[nivel]
            for clave in claves[:cuantos]:
                sec = sectores[clave]
                # El idioma de la campaña es el del país mayoritario de la ola:
                # local y LATAM salen en español (Brasil se atiende en portugués
                # a nivel de correo, ya que el idioma final lo fija el país del
                # decisor); el resto del mundo, en inglés.
                idioma = {"local": "es", "latam": "es", "mundo": "en"}[nivel]
                dolor = _texto(sec["dolores"], idioma)[0]
                salida.append(Campana(
                    id=f"{nivel}-{clave}",
                    nombre=f"{_texto(sec['nombre'], idioma)} · {nivel.upper()}",
                    sector=_texto(sec["nombre"], idioma),
                    nivel=nivel,
                    prioridad=prioridad,
                    paises=codigos,
                    angulo=self._angulo(dolor, empresa, idioma),
                    dolor=dolor,
                    prueba=prueba_base,
                    idioma=idioma,
                ))
        return salida

    @staticmethod
    def _angulo(dolor: str, empresa: Empresa, idioma: str) -> str:
        plantilla = {
            "es": "Para equipos donde {dolor}: {nombre} lo ordena por valor esperado, no por antigüedad.",
            "pt": "Para equipes onde {dolor}: {nombre} organiza por valor esperado, não por antiguidade.",
            "en": "For teams where {dolor}: {nombre} orders the work by expected value, not by age.",
        }[idioma]
        return plantilla.format(dolor=dolor, nombre=empresa.nombre)

    # ------------------------------------------------------------------
    # Fase 4 · encontrar clientes potenciales
    # ------------------------------------------------------------------
    def prospectos(self, empresa: Empresa, campanas: list[Campana],
                   limite: int) -> list[Prospecto]:
        rnd = random.Random(_semilla_de(empresa.dominio))
        sectores = self.datos["sectores"]
        cat_paises = self.datos["paises"]
        raices = self.datos["nombres_empresa"]["raices"]
        modificadores = self.datos["nombres_empresa"]["modificadores"]

        # Cuántos prospectos le toca a cada ola. Uruguay primero y con la
        # mayor tajada: es el mercado donde se puede tocar la puerta. El peso
        # se renormaliza sobre las olas presentes: con el filtro de mercado en
        # «sólo Uruguay» la ola local se lleva el límite entero, no el 45%.
        reparto = {"local": 0.45, "latam": 0.35, "mundo": 0.20}
        presentes = [n for n in ("local", "latam", "mundo")
                     if any(c.nivel == n for c in campanas)]
        peso_total = sum(reparto[n] for n in presentes) or 1.0
        usados: set[str] = set()
        salida: list[Prospecto] = []

        for nivel in presentes:
            campanas_nivel = [c for c in campanas if c.nivel == nivel]
            cupo = max(1, round(limite * reparto[nivel] / peso_total))
            # Peso de cada país dentro de la ola: la densidad de la semilla
            # (Uruguay 1.0, mercados chicos menos) evita listas irreales.
            pares: list[tuple[Campana, str, float]] = []
            for c in campanas_nivel:
                for cod in c.paises:
                    d = cat_paises.get(cod, {}).get("densidad", 0.2)
                    pares.append((c, cod, d))

            # strict=True: _repartir devuelve exactamente una tajada por par;
            # si algún día deja de cumplirlo, que reviente acá y no que se
            # pierdan prospectos en silencio.
            for (campana, cod, _peso), cantidad in zip(
                    pares, _repartir(cupo, [p[2] for p in pares]), strict=True):
                if cantidad <= 0:
                    continue
                clave_sector = campana.id.split("-", 1)[1]
                sec = sectores[clave_sector]
                pais = geo.obtener(cod)
                ciudades = cat_paises.get(cod, {}).get("ciudades", [pais.nombre])
                sufijos = cat_paises.get(cod, {}).get("sufijos", ["S.A."])
                tld = cat_paises.get(cod, {}).get("tld", ".com")
                mods = modificadores.get(clave_sector, ["Group"])
                senales_pool = _texto(sec["senales"], pais.idioma)
                lo, hi = sec["empleados"]

                for _ in range(cantidad):
                    for _intento in range(12):
                        raiz = rnd.choice(raices)
                        mod = rnd.choice(mods)
                        base = f"{mod} {raiz}" if mod[0].isupper() and not mod.startswith("&") \
                            else f"{raiz} {mod}"
                        nombre = f"{base} {rnd.choice(sufijos)}"
                        if nombre not in usados:
                            break
                    else:
                        continue
                    usados.add(nombre)
                    n_senales = rnd.choice([1, 2, 2, 3])
                    senales = rnd.sample(senales_pool, min(n_senales, len(senales_pool)))
                    # Una de cada cinco empresas ya está mirando un competidor:
                    # es la señal que más mueve el score (ver scoring.py).
                    if rnd.random() < 0.2:
                        senales.append({
                            "es": "evalúa herramientas de cobranza automatizada",
                            "pt": "avalia ferramentas de cobrança automatizada",
                            "en": "is evaluating automated collections tools",
                        }[pais.idioma])
                    salida.append(Prospecto(
                        id=f"p{len(salida) + 1:04d}",
                        nombre=nombre,
                        dominio=f"{_slug(base)}{tld}",
                        sector=_texto(sec["nombre"], pais.idioma),
                        pais=cod,
                        ciudad=rnd.choice(ciudades),
                        empleados=rnd.randint(lo, hi),
                        descripcion=_texto(sec["nombre"], pais.idioma) + f" · {rnd.choice(ciudades)}",
                        senales=senales,
                        # El dolor va en el idioma del prospecto, no en el de
                        # la ola: Brasil se trabaja dentro de LATAM (español)
                        # pero se le escribe en portugués.
                        dolor=_texto(sec["dolores"], pais.idioma)[0],
                        campana_id=campana.id,
                        nivel=nivel,
                        prioridad=campana.prioridad,
                        idioma=pais.idioma,
                        sintetico=True,
                        fuente=self.nombre,
                    ))
        return salida

    # ------------------------------------------------------------------
    # Fase 5 · encontrar decisores
    # ------------------------------------------------------------------
    def _seniority(self, cargo: str) -> str:
        c = cargo.lower()
        for pista, valor in self.datos["seniority_por_cargo"].items():
            if pista in c:
                return valor
        return "gerente"

    def decisores(self, prospectos: list[Prospecto], por_empresa: int) -> list[Decisor]:
        sectores = self.datos["sectores"]
        # Índice sector legible → clave, para recuperar los cargos del sector.
        por_nombre: dict[str, str] = {}
        for clave, sec in sectores.items():
            for idioma in geo.IDIOMAS:
                por_nombre[_texto(sec["nombre"], idioma)] = clave

        nombres = self.datos["nombres_persona"]
        salida: list[Decisor] = []
        for prospecto in prospectos:
            rnd = random.Random(_semilla_de(prospecto.dominio))
            clave = por_nombre.get(prospecto.sector, "saas_b2b")
            cargos = sectores[clave]["cargos"]
            idioma = prospecto.idioma if prospecto.idioma in geo.IDIOMAS else "es"
            pila = nombres[f"pila_{idioma}"]
            apellidos = nombres[f"apellido_{idioma}"]
            elegidos = rnd.sample(cargos, min(por_empresa, len(cargos)))
            for cargo in elegidos:
                nombre = f"{rnd.choice(pila)} {rnd.choice(apellidos)}"
                usuario = _slug(nombre.split()[0])[:1] + _slug(nombre.split()[-1])
                salida.append(Decisor(
                    id=f"d{len(salida) + 1:05d}",
                    prospecto_id=prospecto.id,
                    nombre=nombre,
                    cargo=cargo,
                    empresa=prospecto.nombre,
                    pais=prospecto.pais,
                    # Dirección construida con el patrón corporativo del dominio
                    # sintético — no es una casilla real de nadie.
                    email=f"{usuario}@{prospecto.dominio}",
                    linkedin="",
                    seniority=self._seniority(cargo),
                    idioma=idioma,
                    sintetico=True,
                    fuente=self.nombre,
                ))
        return salida
