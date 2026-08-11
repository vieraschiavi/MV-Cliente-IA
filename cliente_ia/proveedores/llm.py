"""
MV Cliente IA · proveedor LLM (Claude / ChatGPT / Gemini / Copilot)
====================================================================
Cubre las fases abiertas —competencia, campañas y listas de empresas
objetivo— consultando el modelo del proveedor elegido. El usuario pega SU
clave en Configuración y elige proveedor:

- **claude**  → API de Anthropic (SDK `anthropic`; default del servidor).
- **openai**  → ChatGPT vía chat completions (REST, sin dependencias).
- **gemini**  → Google Gemini vía generateContent (REST).
- **copilot** → Azure OpenAI (el Copilot "de consumo" no vende clave de API;
  la vía real es un recurso de Azure OpenAI: URL del endpoint + api-key).

Es opcional: sin clave la clase no se instancia y el pipeline sigue con
demo/web, que es el camino que corren los tests.

Dos reglas duras acá:

1. **Empresas sí, personas no.** El LLM propone organizaciones (información
   pública de mercado) pero *nunca* nombres, correos ni perfiles de personas
   reales: la fase 5 queda siempre en manos del proveedor demo, con personas
   sintéticas. Armar una lista de individuos reales con sus datos de contacto
   es exactamente lo que este producto no hace.
2. **Todo lo que sale del LLM se valida** contra el esquema esperado antes de
   entrar al pipeline; lo que no valida se descarta en silencio en vez de
   propagar basura a la interfaz.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from .. import geo
from ..modelos import Campana, Competidor, Empresa, Prospecto
from .base import Proveedor
from .demo import ProveedorDemo

MODELO_DEFAULT = "claude-opus-5"
PROVEEDORES_IA = ("claude", "openai", "gemini", "copilot")
# Modelos por defecto de cada proveedor, pisables por variable de entorno.
# Copilot no lleva: en Azure el modelo lo decide el deployment del endpoint.
MODELOS_IA = {
    "claude": lambda: os.getenv("MVCLIENTE_MODELO", MODELO_DEFAULT),
    "openai": lambda: os.getenv("MVCLIENTE_MODELO_OPENAI", "gpt-4o"),
    "gemini": lambda: os.getenv("MVCLIENTE_MODELO_GEMINI", "gemini-2.5-flash"),
    "copilot": lambda: os.getenv("MVCLIENTE_MODELO_COPILOT", ""),
}
# 180 y no 90: una corrida real desde la app de PC murió con TimeoutError en
# la fase de competencia a los 90 segundos clavados — los modelos con
# razonamiento tardan eso y más con un prompt grande. Pisable por entorno
# para las redes lentas de verdad.
TIMEOUT = int(os.getenv("MVCLIENTE_TIMEOUT_IA", "180"))


class ErrorLLM(RuntimeError):
    pass


def _es_timeout(e: BaseException | None) -> bool:
    """Recorre la cadena de causas buscando un timeout. Un 401 o un JSON
    malformado no merecen reintento; un timeout sí.

    Además de los tipos de la biblioteca estándar se mira el NOMBRE del tipo:
    el SDK de anthropic lanza APITimeoutError envolviendo httpx.ReadTimeout,
    y ninguno de los dos hereda de TimeoutError."""
    import urllib.error

    visto = 0
    while e is not None and visto < 6:
        if isinstance(e, TimeoutError) or "timeout" in type(e).__name__.lower():
            return True
        if isinstance(e, urllib.error.URLError) and \
                isinstance(getattr(e, "reason", None), TimeoutError):
            return True
        e = e.__cause__
        visto += 1
    return False


def hay_clave() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _json_del_texto(texto: str):
    """El modelo a veces envuelve el JSON en ```json … ```. Se limpia y se parsea."""
    t = texto.strip()
    m = re.search(r"```(?:json)?\s*(.+?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    inicio = min((i for i in (t.find("["), t.find("{")) if i >= 0), default=-1)
    if inicio > 0:
        t = t[inicio:]
    try:
        return json.loads(t)
    except json.JSONDecodeError as e:
        # Un array cortado a mitad de un objeto (el modelo se quedó sin
        # aire) todavía sirve: se recorta al último objeto COMPLETO y se
        # cierra. Perder 30 prospectos porque el número 31 vino por la
        # mitad tumbaba la ola entera.
        if t.startswith("["):
            corte = t.rfind("},")
            if corte > 0:
                try:
                    return json.loads(t[:corte + 1] + "]")
                except json.JSONDecodeError:
                    pass
        raise ErrorLLM(f"El modelo no devolvió JSON válido: {e}") from e


class ProveedorLLM(Proveedor):
    nombre = "llm"

    def __init__(self, idioma_base: str = "es", modelo: str = "", clave: str = "",
                 proveedor: str = "claude", endpoint: str = "",
                 mercado: str = "todos", pais_base: str = ""):
        self.proveedor = (proveedor or "claude").lower()
        if self.proveedor not in PROVEEDORES_IA:
            raise ErrorLLM(f"Proveedor de IA desconocido: {proveedor}")
        self.clave = clave or (os.getenv("ANTHROPIC_API_KEY", "")
                               if self.proveedor == "claude" else "")
        if not self.clave:
            raise ErrorLLM(f"Falta la clave de API de {self.proveedor}")
        self.endpoint = (endpoint or "").strip()
        if self.proveedor == "copilot":
            if not self.endpoint.startswith("https://"):
                raise ErrorLLM("Copilot (Azure OpenAI) necesita la URL https "
                               "del endpoint de chat completions")
        self.modelo = modelo or MODELOS_IA[self.proveedor]()
        self.idioma_base = idioma_base
        self.mercado = ("todos" if mercado in (None, "", "todos")
                        else geo.normalizar_nivel(mercado))
        # El mercado propio del cliente. Es lo que decide qué es "local" y qué
        # es "regional" en los prompts: sin esto la competencia se buscaba
        # siempre en Latinoamérica, aunque el cliente vendiera en Alemania.
        self.pais_base = (pais_base or "").strip().upper()
        # Notas informativas (no errores) que el pipeline copia a los avisos
        # de la corrida — p. ej. "ningún competidor tiene base en Uruguay".
        self.notas: list[str] = []
        self._demo = ProveedorDemo(idioma_base)
        # El proveedor viaja en `fuente` y en los avisos: si algo falla, el
        # usuario tiene que ver "openai · competencia: …", no un "llm" mudo.
        if self.proveedor != "claude":
            self.nombre = self.proveedor

    # ------------------------------------------------------------------
    def _post_json(self, url: str, cuerpo: dict, cabeceras: dict) -> dict:
        peticion = urllib.request.Request(
            url, data=json.dumps(cuerpo).encode(),
            headers={"content-type": "application/json", **cabeceras})
        try:
            with urllib.request.urlopen(peticion, timeout=TIMEOUT) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # Sólo código y detalle del cuerpo: nunca la URL (la de Gemini
            # lleva la clave como parámetro). Y la clave se tacha del detalle:
            # OpenAI la repite entera en su mensaje de 401, y este texto va a
            # los avisos de la corrida, que sí se guardan.
            detalle = ""
            try:
                detalle = e.read().decode()[:300]
            except Exception:                            # noqa: BLE001
                pass
            detalle = detalle.replace(self.clave, "•••")[:200]
            raise ErrorLLM(f"{self.proveedor} respondió {e.code}: {detalle}") from e
        except ErrorLLM:
            raise
        except Exception as e:                           # noqa: BLE001
            raise ErrorLLM(f"No se pudo llamar a {self.proveedor}: "
                           f"{type(e).__name__}") from e

    def _pedir(self, prompt: str, max_tokens: int = 8000) -> str:
        """Una llamada al modelo, con UN reintento si lo que falló fue un
        timeout. Antes un timeout suelto tiraba la fase — y con el modo IA
        estricto, la corrida entera que el usuario esperó varios minutos.
        Los errores de verdad (clave mala, respuesta truncada) no se
        reintentan: repetirlos da lo mismo y duplica la espera."""
        try:
            return self._pedir_una_vez(prompt, max_tokens)
        except Exception as e:                           # noqa: BLE001
            # Exception y no sólo ErrorLLM: el timeout del SDK de anthropic
            # sale crudo (APITimeoutError), sin pasar por _post_json.
            if not _es_timeout(e):
                raise
            self.notas.append(
                f"{self.proveedor} no respondió en {TIMEOUT}s; se reintentó "
                "una vez")
            return self._pedir_una_vez(prompt, max_tokens)

    def _pedir_una_vez(self, prompt: str, max_tokens: int = 8000) -> str:
        if self.proveedor == "openai" or self.proveedor == "copilot":
            if self.proveedor == "openai":
                url = "https://api.openai.com/v1/chat/completions"
                cabeceras = {"Authorization": f"Bearer {self.clave}"}
            else:
                url = self.endpoint                      # Azure: deployment en la URL
                cabeceras = {"api-key": self.clave}
            cuerpo = {"messages": [{"role": "user", "content": prompt}],
                      "max_completion_tokens": max_tokens}
            if self.modelo:
                cuerpo["model"] = self.modelo
            d = self._post_json(url, cuerpo, cabeceras)
            try:
                eleccion = d["choices"][0]
                texto = eleccion["message"]["content"] or ""
            except (KeyError, IndexError, TypeError) as e:
                raise ErrorLLM(f"{self.proveedor} devolvió una respuesta "
                               "con forma inesperada") from e
            if eleccion.get("finish_reason") == "length":
                raise ErrorLLM("La respuesta del modelo quedó truncada por el "
                               "límite de tokens — se descarta para no parsear "
                               "JSON a medias")
            return texto

        if self.proveedor == "gemini":
            url = ("https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{self.modelo}:generateContent?key={self.clave}")
            cuerpo = {"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"maxOutputTokens": max_tokens}}
            d = self._post_json(url, cuerpo, {})
            candidatos = d.get("candidates") or []
            if not candidatos:
                raise ErrorLLM("gemini no devolvió candidatos "
                               f"({(d.get('promptFeedback') or {}).get('blockReason', 'sin motivo')})")
            if candidatos[0].get("finishReason") == "MAX_TOKENS":
                raise ErrorLLM("La respuesta del modelo quedó truncada por el "
                               "límite de tokens — se descarta para no parsear "
                               "JSON a medias")
            partes = (candidatos[0].get("content") or {}).get("parts") or []
            return "".join(p.get("text", "") for p in partes)

        return self._pedir_claude(prompt, max_tokens)

    def _pedir_claude_rest(self, prompt: str, max_tokens: int) -> str:
        """Claude sin el SDK, por la API de mensajes. Es el camino de la app
        de PC: el instalador no lleva `anthropic` adentro (son decenas de MB
        para algo que se resuelve con urllib) y sin esto una clave de Claude
        pegada en la app de escritorio no servía para nada."""
        d = self._post_json(
            "https://api.anthropic.com/v1/messages",
            {"model": self.modelo, "max_tokens": max_tokens,
             "messages": [{"role": "user", "content": prompt}]},
            {"x-api-key": self.clave, "anthropic-version": "2023-06-01"})
        if d.get("stop_reason") == "max_tokens":
            raise ErrorLLM("La respuesta del modelo quedó truncada por el "
                           "límite de tokens — se descarta para no parsear "
                           "JSON a medias")
        if d.get("stop_reason") == "refusal":
            raise ErrorLLM("El modelo declinó responder este pedido")
        return "".join(b.get("text", "") for b in (d.get("content") or [])
                       if b.get("type") == "text")

    def _pedir_claude(self, prompt: str, max_tokens: int) -> str:
        try:
            import anthropic
        except ImportError:                            # pragma: no cover - depende del entorno
            return self._pedir_claude_rest(prompt, max_tokens)
        cliente = anthropic.Anthropic(api_key=self.clave, timeout=TIMEOUT)
        # En los modelos Claude actuales el razonamiento viene activado por
        # defecto y CUENTA contra max_tokens: con un tope chico la respuesta
        # salía truncada a mitad del JSON y el parseo fallaba — la corrida
        # caía en silencio a datos sintéticos con la clave andando perfecto.
        # De ahí el tope generoso y el esfuerzo bajo (esto es extracción
        # estructurada, no un problema abierto).
        try:
            r = cliente.messages.create(
                model=self.modelo,
                max_tokens=max_tokens,
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": prompt}],
            )
        except TypeError:
            # SDK viejo sin `output_config`: mismo pedido, esfuerzo default.
            r = cliente.messages.create(
                model=self.modelo,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIStatusError as e:
            raise ErrorLLM(f"La API de Claude respondió {e.status_code}: "
                           f"{getattr(e, 'message', '') or e}") from e
        if r.stop_reason == "max_tokens":
            raise ErrorLLM("La respuesta del modelo quedó truncada por el "
                           "límite de tokens — se descarta para no parsear "
                           "JSON a medias")
        if r.stop_reason == "refusal":
            raise ErrorLLM("El modelo declinó responder este pedido")
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")

    # ------------------------------------------------------------------
    # Fase 1 — la LECTURA del sitio la hace `ProveedorWeb` (es más fiable
    # que pedirle al modelo que recuerde una empresa chica), pero el PERFIL
    # lo afina el modelo con ese texto: ver `perfilar`.
    # ------------------------------------------------------------------
    def perfilar(self, empresa: Empresa) -> Empresa:
        """Deduce el NICHO REAL del texto del sitio.

        La fase 1 leía bien la propuesta de valor, pero categoría, sectores
        objetivo, dolores, diferenciales y tamaño de cliente salían del
        catálogo demo (que es de cobranzas): a un producto de text-to-SQL le
        aparecían «retail con crédito propio» y «mutualistas», siempre los
        mismos sin importar el producto.

        Los textos vuelven en los TRES idiomas porque entran a los correos:
        un correo en portugués con un párrafo en español ya fue una
        regresión una vez.
        """
        prompt = (
            f"{self._contexto_producto(empresa)}\n\n"
            "Deducí del texto real del sitio QUÉ vende esta empresa y a "
            "quién. No uses categorías genéricas tipo «Software B2B»: "
            "nombrá el nicho concreto. Los sectores objetivo tienen que ser "
            "los que COMPRAN este producto en particular.\n\n"
            "Devolvé SOLO un objeto JSON con esta forma exacta:\n"
            "{\n"
            '  "categoria": "el nicho concreto, 2-6 palabras",\n'
            '  "tamano_objetivo": "rango de empleados del cliente típico",\n'
            '  "sectores_objetivo": ["4 a 6 sectores concretos que compran esto"],\n'
            '  "textos": {\n'
            '    "es": {"propuesta": "qué hace, una frase, SIN el nombre de la '
            'empresa adelante", "dolores": ["3-4 dolores reales del comprador"], '
            '"diferenciales": ["2-4 diferenciales que el sitio sostenga"]},\n'
            '    "pt": {"propuesta": "...", "dolores": ["..."], "diferenciales": ["..."]},\n'
            '    "en": {"propuesta": "...", "dolores": ["..."], "diferenciales": ["..."]}\n'
            "  }\n"
            "}\n"
            "Los tres idiomas dicen LO MISMO, cada uno bien escrito en su "
            "idioma (no traducción literal). Nada de superlativos ni de "
            "inventar funciones que el sitio no menciona."
        )
        datos = _json_del_texto(self._pedir(prompt, 8000))
        if not isinstance(datos, dict):
            raise ErrorLLM("El perfil no volvió con la forma esperada")

        def _lista(x, tope):
            return [str(i).strip() for i in x if str(i).strip()][:tope] \
                if isinstance(x, list) else []

        sectores = _lista(datos.get("sectores_objetivo"), 6)
        if not sectores:
            # Sin sectores no hay perfil que valga: se deja el del catálogo
            # y el aviso explica por qué (mejor eso que medio perfil).
            raise ErrorLLM("El modelo no devolvió sectores objetivo del producto")

        crudos = datos.get("textos") or {}
        textos = {i: dict(empresa.textos.get(i, {})) for i in geo.IDIOMAS}
        for idioma in geo.IDIOMAS:
            de_idioma = crudos.get(idioma)
            if not isinstance(de_idioma, dict):
                continue
            propuesta = str(de_idioma.get("propuesta", "")).strip()
            if propuesta:
                # El nombre lo antepone la plantilla del correo; si el modelo
                # lo puso igual, quedaba escrito dos veces seguidas.
                if empresa.nombre and propuesta.lower().startswith(empresa.nombre.lower()):
                    propuesta = propuesta[len(empresa.nombre):].lstrip(" ,:—-")
                textos[idioma]["propuesta"] = propuesta[0].lower() + propuesta[1:] \
                    if propuesta else propuesta
            dolores = _lista(de_idioma.get("dolores"), 4)
            if dolores:
                textos[idioma]["dolores"] = dolores
            difs = _lista(de_idioma.get("diferenciales"), 4)
            if difs:
                textos[idioma]["diferenciales"] = difs

        idioma_base = self.idioma_base if self.idioma_base in geo.IDIOMAS else "es"
        empresa.categoria = str(datos.get("categoria", "")).strip() or empresa.categoria
        empresa.tamano_objetivo = (str(datos.get("tamano_objetivo", "")).strip()
                                   or empresa.tamano_objetivo)
        empresa.sectores_objetivo = sectores
        empresa.textos = textos
        base = textos.get(idioma_base, {})
        empresa.dolores = list(base.get("dolores") or empresa.dolores)
        empresa.diferenciales = list(base.get("diferenciales") or empresa.diferenciales)
        if base.get("propuesta"):
            empresa.propuesta = f"{empresa.nombre} {base['propuesta']}".strip().rstrip(".") + "."
        empresa.fuente = self.nombre
        return empresa


    def _contexto_producto(self, empresa: Empresa) -> str:
        """El producto REAL, con el texto del propio sitio adelante: es la
        diferencia entre buscar en el rubro correcto o en el del catálogo."""
        partes = []
        if empresa.resumen_sitio:
            partes.append("Texto real extraído de la web del producto:\n"
                          f"{empresa.resumen_sitio}")
        partes.append(f"Empresa: {empresa.nombre} ({empresa.dominio}). "
                      f"Propuesta: {empresa.propuesta}")
        return "\n\n".join(partes)

    # Fase 2 · competencia
    def competencia(self, empresa: Empresa) -> list[Competidor]:
        # El recorte geográfico manda también acá: un competidor que no opera
        # donde vende el cliente no le saca clientes. Sin filtro, el país de
        # origen va primero igual — es donde la competencia duele.
        pais = (self.pais_base or empresa.pais or "UY").upper()
        nombre_pais = geo.nombre_pais(pais, self.idioma_base)
        region = geo.nombre_region(geo.region_de(pais), self.idioma_base)
        recorte = {
            "todos": (f"Priorizá así: primero competidores de {nombre_pais} o que "
                      f"operen en {nombre_pais}, después los regionales de "
                      f"{region}, y recién al final los globales — y sólo "
                      f"si de verdad venden en el mercado de {nombre_pais}."),
            geo.NIVEL_LOCAL: (
                f"SOLO competidores que operen en {nombre_pais}: locales o "
                f"internacionales con presencia real en {nombre_pais}. Ninguno "
                "que no le pueda sacar un cliente ahí."),
            geo.NIVEL_REGIONAL: (
                f"SOLO competidores que operen en {region}: locales "
                "de la región o internacionales con presencia real en "
                "ella."),
            geo.NIVEL_MUNDO: (f"Competidores del mercado global, fuera de "
                              f"{region} incluida."),
        }[self.mercado]
        prompt = (
            "Sos analista de mercado y tenés que identificar COMPETIDORES "
            "DIRECTOS.\n\n"
            f"{self._contexto_producto(empresa)}\n\n"
            "Primero deducí, del texto real de la web, qué producto o servicio "
            "concreto vende esta empresa y a qué tipo de cliente. Después listá "
            "hasta 12 competidores DIRECTOS, reales y verificables: empresas que "
            "venden ESE MISMO tipo de producto o servicio a un cliente "
            "comparable. La prueba: un cliente podría contratar a esta empresa "
            "O al competidor para resolver el mismo problema. NO incluyas "
            "empresas de rubros vecinos, proveedores, clientes del rubro ni "
            f"marketplaces genéricos.\n{recorte}\n"
            "Devolvé SOLO un array JSON, sin texto alrededor, con objetos: "
            '{"dominio": "ejemplo.com", "nombre": "Ejemplo", "posicionamiento": '
            '"una frase", "pais": "US", "vende_en_objetivo": true, '
            '"solapamiento": 0.0-1.0} — `pais` es dónde tiene su base la '
            f"empresa, `vende_en_objetivo` es si de verdad le vende a clientes "
            f"del recorte pedido, y el solapamiento mide qué tan directo es el "
            "competidor. Si no estás seguro de que una empresa existe o de que "
            "compite de verdad, no la incluyas."
        )
        datos = _json_del_texto(self._pedir(prompt, 8000))
        salida: list[Competidor] = []
        vende_ahi: dict[str, bool] = {}
        for c in datos if isinstance(datos, list) else []:
            if not isinstance(c, dict) or not c.get("dominio"):
                continue
            dominio = str(c["dominio"]).strip().lower()
            vende_ahi[dominio] = bool(c.get("vende_en_objetivo", True))
            salida.append(Competidor(
                dominio=dominio,
                nombre=str(c.get("nombre", "")).strip(),
                posicionamiento=str(c.get("posicionamiento", "")).strip(),
                pais=str(c.get("pais", "")).strip().upper()[:2],
                solapamiento=max(0.0, min(1.0, float(c.get("solapamiento", 0.5) or 0))),
                fuente=self.nombre,
            ))
        # Con filtro local/LATAM, si la primera pasada no trajo NINGUNO con
        # base en el recorte, se insiste con una pasada dedicada antes de
        # conformarse con los regionales: los competidores de un mercado
        # chico suelen ser empresas chicas que el modelo no nombra salvo que
        # se le pregunte por ellas en concreto (pasó con «sólo Uruguay»: diez
        # competidores, todos AR/CO/BR/US).
        objetivo = self._paises_objetivo(pais)
        if objetivo and not any(c.pais in objetivo for c in salida):
            vistos = {c.dominio for c in salida}
            for c in self._competencia_local(empresa, sorted(objetivo)):
                if c.dominio not in vistos:
                    vende_ahi[c.dominio] = True
                    salida.append(c)
        return self._recortar_competencia(salida, vende_ahi, pais)

    def _idioma_mayoritario(self, codigos: list[str]) -> str:
        """El idioma que habla la mayoría de los países de una ola."""
        conteo: dict[str, int] = {}
        for cod in codigos:
            idi = geo.idioma_de(cod)
            conteo[idi] = conteo.get(idi, 0) + 1
        if not conteo:
            return self.idioma_base if self.idioma_base in geo.IDIOMAS else "es"
        return max(sorted(conteo), key=lambda i: conteo[i])

    def _paises_objetivo(self, pais: str) -> set[str]:
        """Países del recorte del mercado elegido; vacío = sin recorte.
        La ola regional es la del país base: para un cliente alemán son los
        países de Europa, no los de Latinoamérica."""
        if self.mercado == geo.NIVEL_LOCAL:
            return {pais}
        if self.mercado == geo.NIVEL_REGIONAL:
            return {c for n, _p, cods in geo.orden_de_olas(pais)
                    if n == geo.NIVEL_REGIONAL for c in cods} | {pais}
        return set()

    def _competencia_local(self, empresa: Empresa, paises: list[str]) -> list[Competidor]:
        """Segunda pasada con foco exclusivo en el recorte pedido."""
        prompt = (
            f"{self._contexto_producto(empresa)}\n\n"
            f"Segunda pasada, foco exclusivo: empresas CON BASE en "
            f"{', '.join(paises)} que vendan el MISMO tipo de producto o "
            "servicio. En un mercado chico los competidores directos suelen "
            "ser empresas chicas, estudios o software local poco conocido: "
            "si existen de verdad, nombralos aunque sean pequeños. Si no "
            "conocés NINGUNA empresa con base ahí con certeza, devolvé [] — "
            "no rellenes con regionales ni globales.\n"
            "Devolvé SOLO un array JSON con objetos: "
            '{"dominio": "ejemplo.com", "nombre": "Ejemplo", "posicionamiento": '
            '"una frase", "pais": "UY", "solapamiento": 0.0-1.0}'
        )
        try:
            datos = _json_del_texto(self._pedir(prompt, 8000))
        except ErrorLLM:
            return []                                    # la primera pasada ya alcanza
        salida = []
        for c in datos if isinstance(datos, list) else []:
            if not isinstance(c, dict) or not c.get("dominio"):
                continue
            cod = str(c.get("pais", "")).strip().upper()[:2]
            if cod not in paises:
                continue                                 # el foco era ESE recorte
            salida.append(Competidor(
                dominio=str(c["dominio"]).strip().lower(),
                nombre=str(c.get("nombre", "")).strip(),
                posicionamiento=str(c.get("posicionamiento", "")).strip(),
                pais=cod,
                solapamiento=max(0.0, min(1.0, float(c.get("solapamiento", 0.5) or 0))),
                fuente=self.nombre,
            ))
        return salida

    def _recortar_competencia(self, competidores: list[Competidor],
                              vende_ahi: dict[str, bool], pais: str) -> list[Competidor]:
        """El filtro de mercado se hace CUMPLIR acá, no sólo se pide en el
        prompt: con «sólo mi país» aparecían doce competidores globales sin
        una línea que dijera dónde operaban. Los de casa van primero; los que
        ni venden en el recorte se caen."""
        if self.mercado in ("todos", geo.NIVEL_MUNDO):
            return sorted(competidores, key=lambda c: -c.solapamiento)

        objetivo = self._paises_objetivo(pais)
        de_casa = [c for c in competidores if c.pais in objetivo]
        venden = [c for c in competidores
                  if c.pais not in objetivo and vende_ahi.get(c.dominio, True)]
        if not de_casa and venden:
            # Mercado chico: puede no haber ni un competidor con base local.
            # Decirlo vale más que devolver una lista global sin contexto.
            donde = (geo.nombre_pais(pais, self.idioma_base) if self.mercado == geo.NIVEL_LOCAL
                     else geo.nombre_region(geo.region_de(pais), self.idioma_base))
            self.notas.append(
                f"Competencia: ninguno de los competidores directos tiene base "
                f"en {donde}; los que se listan son de afuera pero venden ahí.")
        return (sorted(de_casa, key=lambda c: -c.solapamiento)
                + sorted(venden, key=lambda c: -c.solapamiento))

    # Fase 3 · campañas — antes sólo se le pedía el ángulo al modelo y los
    # sectores/dolores salían del catálogo demo (que es de cobranzas): a una
    # inmobiliaria le aparecían campañas de "cuotas vencidas". Ahora el modelo
    # define sector, dolor y ángulo desde el producto REAL; la estructura de
    # olas (niveles, países, prioridad) sigue siendo la de siempre.
    def campanas(self, empresa: Empresa, competidores: list[Competidor]) -> list[Campana]:
        from .demo import SECTORES_POR_NIVEL, _slug

        base = (self.pais_base or empresa.pais or "UY").upper()
        nombre_pais = geo.nombre_pais(base, self.idioma_base)
        region = geo.nombre_region(geo.region_de(base), self.idioma_base)
        olas = [(n, p, c) for n, p, c in geo.orden_de_olas(base) if c]
        # El idioma de cada ola sale de los países que la componen, no de una
        # tabla fija: la ola regional de un cliente alemán se escribe en inglés,
        # la de un uruguayo en español.
        idioma_ola = {nivel: self._idioma_mayoritario(codigos)
                      for nivel, _p, codigos in olas}
        pedido = [{"nivel": nivel, "campanas": SECTORES_POR_NIVEL[nivel],
                   "idioma": idioma_ola[nivel]}
                  for nivel, _prioridad, _codigos in olas]
        rivales = "; ".join(f"{c.nombre} ({c.posicionamiento})"
                            for c in competidores[:6] if c.nombre)
        prompt = (
            f"{self._contexto_producto(empresa)}\n\n"
            + (f"Competidores directos ya identificados: {rivales}\n\n" if rivales else "")
            + "Definí campañas de salida al mercado para ESTE producto. Para "
            "cada recorte de esta lista, la cantidad indicada de campañas:\n"
            f"{json.dumps(pedido, ensure_ascii=False)}\n"
            f"(local = {nombre_pais}, regional = el resto de {region}, "
            f"mundo = el resto del mundo)\n\n"
            "Cada campaña: `sector` = tipo concreto de organización que COMPRA "
            "este producto (no rubros vecinos), `dolor` = el problema de ese "
            "sector que este producto resuelve, `angulo` = UNA frase comercial "
            "concreta y sin superlativos. Todo en el `idioma` del recorte. "
            "Devolvé SOLO un array JSON: "
            '[{"nivel": "local", "sector": "...", "dolor": "...", "angulo": "..."}]'
        )
        datos = _json_del_texto(self._pedir(prompt, 8000))
        por_ola = {nivel: (prioridad, codigos) for nivel, prioridad, codigos in olas}
        prueba = (empresa.diferenciales or [""])[0]
        salida: list[Campana] = []
        vistos: set[str] = set()
        for c in datos if isinstance(datos, list) else []:
            if not isinstance(c, dict):
                continue
            nivel = geo.normalizar_nivel(c.get("nivel"))
            sector = str(c.get("sector", "")).strip()
            if nivel not in por_ola or not sector:
                continue
            cid = f"{nivel}-{_slug(sector)[:24]}"
            if cid in vistos:
                continue
            vistos.add(cid)
            prioridad, codigos = por_ola[nivel]
            idioma = idioma_ola[nivel]
            etiqueta = {geo.NIVEL_LOCAL: nombre_pais,
                        geo.NIVEL_REGIONAL: region,
                        geo.NIVEL_MUNDO: "Mundo"}[nivel]
            salida.append(Campana(
                id=cid,
                nombre=f"{sector} · {etiqueta.upper()}",
                sector=sector,
                nivel=nivel,
                prioridad=prioridad,
                paises=codigos,
                angulo=str(c.get("angulo", "")).strip(),
                dolor=str(c.get("dolor", "")).strip(),
                prueba=prueba,
                idioma=idioma,
            ))
        # Sin campañas útiles se deja subir el error: la cadena cae al demo
        # (que al menos es coherente consigo mismo) y el aviso explica por qué.
        if not salida:
            raise ErrorLLM("El modelo no devolvió campañas utilizables")
        return salida

    # Fase 4 · empresas objetivo reales
    def prospectos(self, empresa: Empresa, campanas: list[Campana],
                   limite: int) -> list[Prospecto]:
        salida: list[Prospecto] = []
        fallos: list[str] = []
        # El cupo se reparte con el país del cliente primero. Se renormaliza
        # sobre las olas PRESENTES: con el filtro de mercado en «sólo mi país»
        # la ola local se lleva el límite entero, no el 45%.
        reparto = {geo.NIVEL_LOCAL: 0.45, geo.NIVEL_REGIONAL: 0.35,
                   geo.NIVEL_MUNDO: 0.20}
        niveles = [n for n in geo.NIVELES
                   if any(c.nivel == n for c in campanas)]
        peso_total = sum(reparto[n] for n in niveles) or 1.0

        def _pedir_ola(nivel: str):
            del_nivel = [c for c in campanas if c.nivel == nivel]
            cupo = max(1, round(limite * reparto[nivel] / peso_total))
            paises = sorted({p for c in del_nivel for p in c.paises})
            prompt = (
                f"{self._contexto_producto(empresa)}\n\n"
                "Pensá primero qué tipo de organización COMPRA este producto o "
                "servicio: quién tiene el problema que resuelve y presupuesto "
                "para pagarlo. Los sectores objetivo los decidís vos a partir "
                "del producto real — no busques empresas de otros rubros.\n"
                f"Países del recorte (excluyente): {', '.join(paises)}.\n\n"
                f"Listá hasta {cupo} organizaciones REALES de esos países que "
                "sean compradoras plausibles de ESTE producto. Devolvé SOLO un "
                "array JSON con objetos: "
                '{"nombre": "...", "dominio": "ejemplo.com", "sector": "...", '
                '"pais": "UY", "ciudad": "...", "empleados": 300, "senales": ["..."]}. '
                "`senales` son hechos públicos y comprobables de por qué es buen momento "
                "para contactarlas. No inventes: si no conocés la organización, omitila. "
                "NO incluyas nombres de personas."
            )
            return _json_del_texto(self._pedir(prompt, 10000))

        # Las tres olas van EN PARALELO: en serie eran tres llamadas al modelo
        # una detrás de otra y la corrida entera rozaba el timeout de una
        # función serverless — el usuario veía "Buscando…" hasta el corte.
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=len(niveles) or 1) as pool:
            futuros = {n: pool.submit(_pedir_ola, n) for n in niveles}

        for nivel in niveles:                        # orden de olas, siempre
            del_nivel = [c for c in campanas if c.nivel == nivel]
            paises = sorted({p for c in del_nivel for p in c.paises})
            try:
                datos = futuros[nivel].result()
            except ErrorLLM as e:
                # Una ola puede fallar y las otras salvar la fase; pero si
                # fallan TODAS, el motivo tiene que subir como aviso en vez
                # de devolver [] mudo y caer al demo sin explicación.
                fallos.append(f"{nivel}: {e}")
                continue
            por_sector = {c.sector: c for c in del_nivel}
            for p in datos if isinstance(datos, list) else []:
                if not isinstance(p, dict) or not p.get("nombre") or not p.get("dominio"):
                    continue
                cod = str(p.get("pais", "")).strip().upper()[:2]
                if cod not in paises:
                    continue                              # fuera del recorte de la ola
                campana = por_sector.get(str(p.get("sector", "")).strip()) or del_nivel[0]
                pais = geo.obtener(cod)
                salida.append(Prospecto(
                    id=f"p{len(salida) + 1:04d}",
                    nombre=str(p["nombre"]).strip(),
                    dominio=str(p["dominio"]).strip().lower(),
                    sector=str(p.get("sector") or campana.sector).strip(),
                    pais=cod,
                    ciudad=str(p.get("ciudad", "")).strip(),
                    empleados=int(p.get("empleados") or 0),
                    descripcion=str(p.get("descripcion", "")).strip(),
                    senales=[str(s) for s in (p.get("senales") or [])][:5],
                    campana_id=campana.id,
                    nivel=nivel,
                    prioridad=campana.prioridad,
                    idioma=pais.idioma,
                    sintetico=False,
                    fuente=self.nombre,
                ))
        if not salida and fallos:
            raise ErrorLLM("; ".join(fallos))
        return salida

    # Fase 5 · NO la implementa a propósito: las personas las genera el
    # proveedor demo, sintéticas y marcadas como tales (ver docstring).
