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
TIMEOUT = 90


class ErrorLLM(RuntimeError):
    pass


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
        raise ErrorLLM(f"El modelo no devolvió JSON válido: {e}") from e


class ProveedorLLM(Proveedor):
    nombre = "llm"

    def __init__(self, idioma_base: str = "es", modelo: str = "", clave: str = "",
                 proveedor: str = "claude", endpoint: str = ""):
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

    def _pedir_claude(self, prompt: str, max_tokens: int) -> str:
        try:
            import anthropic
        except ImportError as e:                       # pragma: no cover - depende del entorno
            raise ErrorLLM("Falta el paquete `anthropic` (pip install anthropic)") from e
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
    # Fase 1 — la deja a `ProveedorWeb`/demo: leer el sitio es más fiable
    # que pedirle al modelo que recuerde una empresa chica.
    # ------------------------------------------------------------------

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
        prompt = (
            "Sos analista de mercado y tenés que identificar COMPETIDORES "
            "DIRECTOS.\n\n"
            f"{self._contexto_producto(empresa)}\n\n"
            "Primero deducí, del texto real de la web, qué producto o servicio "
            "concreto vende esta empresa y a qué tipo de cliente. Después listá "
            "hasta 12 competidores DIRECTOS, reales y verificables: empresas que "
            "venden ESE MISMO tipo de producto o servicio a un cliente "
            "comparable. NO incluyas empresas de rubros vecinos, proveedores, "
            "clientes del rubro ni marketplaces genéricos. "
            "Devolvé SOLO un array JSON, sin texto alrededor, con objetos: "
            '{"dominio": "ejemplo.com", "nombre": "Ejemplo", "posicionamiento": '
            '"una frase", "pais": "US", "solapamiento": 0.0-1.0} — el '
            "solapamiento mide qué tan directo es el competidor. Si no estás "
            "seguro de que una empresa existe o de que compite de verdad, no "
            "la incluyas."
        )
        datos = _json_del_texto(self._pedir(prompt, 8000))
        salida: list[Competidor] = []
        for c in datos if isinstance(datos, list) else []:
            if not isinstance(c, dict) or not c.get("dominio"):
                continue
            salida.append(Competidor(
                dominio=str(c["dominio"]).strip().lower(),
                nombre=str(c.get("nombre", "")).strip(),
                posicionamiento=str(c.get("posicionamiento", "")).strip(),
                pais=str(c.get("pais", "")).strip().upper()[:2],
                solapamiento=max(0.0, min(1.0, float(c.get("solapamiento", 0.5) or 0))),
                fuente=self.nombre,
            ))
        return sorted(salida, key=lambda c: -c.solapamiento)

    # Fase 3 · campañas — se apoya en la estructura de olas del demo y sólo
    # le pide al modelo el ángulo del mensaje, que es lo que aporta valor.
    def campanas(self, empresa: Empresa, competidores: list[Competidor]) -> list[Campana]:
        base = self._demo.campanas(empresa, competidores)
        resumen = [{"id": c.id, "sector": c.sector, "nivel": c.nivel,
                    "idioma": c.idioma, "dolor": c.dolor} for c in base]
        prompt = (
            f"Producto: {empresa.nombre} — {empresa.propuesta}\n"
            f"Diferenciales: {'; '.join(empresa.diferenciales)}\n\n"
            f"Para cada campaña de esta lista escribí un ángulo comercial de UNA frase, "
            f"en el idioma indicado en el campo `idioma`, concreto y sin superlativos:\n"
            f"{json.dumps(resumen, ensure_ascii=False)}\n\n"
            'Devolvé SOLO un array JSON: [{"id": "...", "angulo": "..."}]'
        )
        try:
            datos = _json_del_texto(self._pedir(prompt, 8000))
        except ErrorLLM:
            return base                                  # el ángulo del demo alcanza
        angulos = {str(d.get("id")): str(d.get("angulo", "")).strip()
                   for d in datos if isinstance(d, dict)}
        for c in base:
            if angulos.get(c.id):
                c.angulo = angulos[c.id]
        return base

    # Fase 4 · empresas objetivo reales
    def prospectos(self, empresa: Empresa, campanas: list[Campana],
                   limite: int) -> list[Prospecto]:
        salida: list[Prospecto] = []
        fallos: list[str] = []
        # El cupo se reparte con Uruguay primero. Se renormaliza sobre las
        # olas PRESENTES: con el filtro de mercado en «sólo Uruguay» la ola
        # local se lleva el límite entero, no el 45%.
        reparto = {"local": 0.45, "latam": 0.35, "mundo": 0.20}
        niveles = [n for n in ("local", "latam", "mundo")
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
