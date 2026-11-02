"""
MV Cliente IA · marketing digital del cliente (pestaña Marketing digital)
=========================================================================
Una auditoría de la presencia digital del PROPIO cliente —su sitio y sus
redes— puesta al lado de su competencia, con los KPI que salen de eso.

Reglas que no se negocian, las mismas que el resto del producto:

- **Todo se mide, nada se estima.** Cada dato sale de leer el sitio real (el
  mismo `bajar` del motor, con su bloqueo de direcciones internas) o de las
  cifras públicas de sus redes (`redes_publicas`). Lo que no se pudo leer
  vuelve como `None` y la interfaz dice «no se pudo medir», no un cero.
- **El puntaje es una suma con pesos DECLARADOS** (`PESOS`), que viajan en
  la respuesta para que la interfaz los muestre: es una regla a la vista,
  no la opinión de un modelo.
- **Las recomendaciones son reglas**, una por hallazgo, con un código que la
  interfaz traduce a es/pt/en (regla 3 del proyecto: el idioma manda).
- **Es una acción del usuario, fuera del pipeline.** El modo demo sigue sin
  salir a la red (regla 7): esto corre sólo cuando alguien aprieta «Auditar».
"""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from html import unescape

TIMEOUT = 8
MAX_COMPETIDORES = 6

PESOS = {"seo": 30, "medicion": 20, "conversion": 20, "redes": 15, "tecnica": 15}

# Etiquetas de medición y publicidad: (clave, patrón en el HTML). Si el sitio
# las carga desde un gestor por JavaScript puro, no se ven en el HTML crudo:
# por eso la interfaz dice «detectadas», no «instaladas».
MEDICION = (
    ("ga4", r"gtag/js\?id=G-|['\"]G-[A-Z0-9]{6,}['\"]"),
    ("gtm", r"googletagmanager\.com/gtm\.js|GTM-[A-Z0-9]{4,}"),
    ("google_ads", r"googleadservices\.com|['\"]AW-\d{6,}"),
    ("meta_pixel", r"connect\.facebook\.net/[^\"']*/fbevents\.js|fbq\(\s*['\"]init"),
    ("linkedin_insight", r"snap\.licdn\.com|_linkedin_partner_id"),
    ("tiktok_pixel", r"analytics\.tiktok\.com"),
    ("hotjar", r"static\.hotjar\.com|hotjar\.com/c/hotjar"),
    ("clarity", r"clarity\.ms/tag"),
    ("hubspot", r"js\.hs-scripts\.com|js\.hsforms\.net"),
)
CHAT = r"widget\.intercom\.io|js\.driftt\.com|client\.crisp\.chat|embed\.tawk\.to|static\.zdassets\.com|js\.hs-banner\.com|livechatinc\.com"
CTA = (r"\b(demo|agend|cotiz|prob(a|á)|empez|comenz|contrat|suscrib|registr|"
       r"free trial|get started|book|start|sign ?up|request|teste|experiment|comece|assin)")

_RE_TAG = re.compile(r"<[^>]+>")


def _texto(html: str) -> str:
    return " ".join(unescape(_RE_TAG.sub(" ", html or "")).split())


def _meta(html: str, nombre: str) -> str:
    for patron in (rf'<meta[^>]+(?:name|property)=["\']{nombre}["\'][^>]*content=["\']([^"\']*)',
                   rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:name|property)=["\']{nombre}["\']'):
        m = re.search(patron, html, re.I)
        if m:
            return " ".join(unescape(m.group(1)).split())
    return ""


def _tipos_schema(html: str) -> list[str]:
    tipos: set[str] = set()
    for bloque in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.I | re.S):
        try:
            datos = json.loads(bloque.strip())
        except ValueError:
            continue
        pila = [datos]
        while pila:
            x = pila.pop()
            if isinstance(x, list):
                pila.extend(x)
            elif isinstance(x, dict):
                t = x.get("@type")
                tipos.update([t] if isinstance(t, str) else [s for s in (t or []) if isinstance(s, str)])
                pila.extend(v for v in x.values() if isinstance(v, (dict, list)))
    return sorted(tipos)[:12]


def seo_de_html(html: str) -> dict:
    """SEO on-page: lo que Google y quien comparte el enlace leen primero."""
    titulo = " ".join(unescape(m.group(1)).split()) if (
        m := re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)) else ""
    descripcion = _meta(html, "description")
    imagenes = re.findall(r"<img\b[^>]*>", html, re.I)
    sin_alt = [i for i in imagenes if not re.search(r'\balt=["\'][^"\']+', i, re.I)]
    idiomas = sorted(set(re.findall(r'hreflang=["\']([a-zA-Z-]{2,10})', html)))
    lang = m.group(1) if (m := re.search(r'<html[^>]+lang=["\']([a-zA-Z-]{2,10})', html, re.I)) else ""
    return {
        "titulo": titulo[:200], "largo_titulo": len(titulo),
        "descripcion": descripcion[:300], "largo_descripcion": len(descripcion),
        "h1": len(re.findall(r"<h1\b", html, re.I)),
        "canonical": bool(re.search(r'rel=["\']canonical["\']', html, re.I)),
        "viewport": bool(re.search(r'name=["\']viewport["\']', html, re.I)),
        "open_graph": bool(_meta(html, "og:title")) and bool(_meta(html, "og:image")),
        "twitter_card": bool(_meta(html, "twitter:card")),
        "schema": _tipos_schema(html),
        "lang": lang, "idiomas": idiomas,
        "imagenes": len(imagenes), "imagenes_sin_alt": len(sin_alt),
        "favicon": bool(re.search(r'rel=["\'][^"\']*icon', html, re.I)),
        "palabras": len(_texto(html).split()),
    }


def medicion_de_html(html: str) -> dict[str, bool]:
    return {clave: bool(re.search(patron, html, re.I)) for clave, patron in MEDICION}


def conversion_de_html(html: str) -> dict:
    formularios = re.findall(r"<form\b.*?</form>", html, re.I | re.S)
    con_email = [f for f in formularios if re.search(r'type=["\']email|name=["\'][^"\']*mail', f, re.I)]
    botones = [_texto(b) for b in re.findall(r"<(?:a|button)\b[^>]*>(.*?)</(?:a|button)>", html, re.I | re.S)]
    return {
        "formulario": bool(con_email),
        "whatsapp": bool(re.search(r"wa\.me/|api\.whatsapp\.com/send|whatsapp://", html, re.I)),
        "email": bool(re.search(r'href=["\']mailto:', html, re.I)),
        "telefono": bool(re.search(r'href=["\']tel:', html, re.I)),
        "chat": bool(re.search(CHAT, html, re.I)),
        "cta": sum(1 for b in botones if b and len(b) < 60 and re.search(CTA, b, re.I)),
    }


def _puntaje_seo(s: dict) -> int:
    reglas = (30 <= s["largo_titulo"] <= 65, 70 <= s["largo_descripcion"] <= 160,
              s["h1"] == 1, s["canonical"], s["viewport"], s["open_graph"],
              bool(s["schema"]), bool(s["lang"]),
              s["imagenes"] == 0 or s["imagenes_sin_alt"] / s["imagenes"] <= 0.2,
              s["palabras"] >= 300)
    return round(100 * sum(reglas) / len(reglas))


def _puntaje_tecnica(t: dict) -> int | None:
    if t.get("ms") is None:
        return None
    reglas = (t["https"], t["ms"] <= 1500, t["kb"] <= 1500,
              bool(t.get("robots")), bool(t.get("sitemap")))
    return round(100 * sum(reglas) / len(reglas))


def _puntaje_redes(redes: dict, metricas: dict) -> int:
    perfiles = sum(1 for r in ("linkedin", "instagram", "facebook", "tiktok") if redes.get(r))
    con_cifra = sum(1 for m in metricas.values() if m.get("estado") == "ok")
    return min(100, perfiles * 20 + con_cifra * 5)


def puntajes(a: dict) -> dict:
    """Subpuntajes 0-100 y el total ponderado. Un área que no se pudo medir
    sale del promedio en vez de contar como cero."""
    sub = {
        "seo": _puntaje_seo(a["seo"]),
        "medicion": min(100, 25 * sum(a["medicion"].values())),
        "conversion": min(100, 20 * sum(bool(v) for k, v in a["conversion"].items() if k != "cta")
                          + (20 if a["conversion"]["cta"] else 0)),
        "redes": _puntaje_redes(a.get("redes", {}), a.get("metricas", {})),
        "tecnica": _puntaje_tecnica(a["tecnica"]),
    }
    medidos = {k: v for k, v in sub.items() if v is not None}
    peso = sum(PESOS[k] for k in medidos)
    total = round(sum(v * PESOS[k] for k, v in medidos.items()) / peso) if peso else None
    return {"sub": sub, "total": total}


def recomendaciones(a: dict) -> list[dict]:
    """Una por hallazgo, de la más rentable a la menos. `codigo` lo traduce
    la interfaz; `datos` lleva los números que la frase necesita."""
    s, m, c, t = a["seo"], a["medicion"], a["conversion"], a["tecnica"]
    reglas = [
        ("alta", "sin_analitica", not (m["ga4"] or m["gtm"]), {}),
        ("alta", "sin_formulario", not c["formulario"] and not c["whatsapp"], {}),
        ("alta", "sin_cta", c["cta"] == 0, {}),
        ("alta", "sin_https", t.get("ms") is not None and not t["https"], {}),
        ("media", "titulo", not 30 <= s["largo_titulo"] <= 65, {"n": s["largo_titulo"]}),
        ("media", "descripcion", not 70 <= s["largo_descripcion"] <= 160, {"n": s["largo_descripcion"]}),
        ("media", "h1", s["h1"] != 1, {"n": s["h1"]}),
        ("media", "sin_pixel", not (m["meta_pixel"] or m["linkedin_insight"] or m["tiktok_pixel"]), {}),
        ("media", "lento", (t.get("ms") or 0) > 1500, {"ms": t.get("ms")}),
        ("media", "pesado", (t.get("kb") or 0) > 1500, {"kb": t.get("kb")}),
        ("media", "sin_redes", not any(a.get("redes", {}).get(r) for r in
                                       ("linkedin", "instagram", "facebook", "tiktok")), {}),
        ("baja", "open_graph", not s["open_graph"], {}),
        ("baja", "schema", not s["schema"], {}),
        ("baja", "alt", s["imagenes"] and s["imagenes_sin_alt"] / s["imagenes"] > 0.2,
         {"n": s["imagenes_sin_alt"], "total": s["imagenes"]}),
        ("baja", "sitemap", t.get("ms") is not None and not t.get("sitemap"), {}),
        ("baja", "contenido", s["palabras"] < 300, {"n": s["palabras"]}),
        ("baja", "whatsapp", not c["whatsapp"], {}),
    ]
    return [{"prioridad": p, "codigo": cod, "datos": d} for p, cod, cond, d in reglas if cond]


def _bajar_medido(url: str, bajar) -> tuple[str, int | None]:
    inicio = time.monotonic()
    html = bajar(url, TIMEOUT)
    return html, round((time.monotonic() - inicio) * 1000)


def _existe(url: str, bajar, marca: str) -> bool:
    try:
        return marca in bajar(url, TIMEOUT).lower()
    except Exception:                                    # noqa: BLE001
        return False


def auditar_sitio(dominio: str, bajar=None, completo: bool = True) -> dict:
    """La auditoría de un sitio. `completo=False` (para la competencia) se
    salta robots/sitemap: alcanza con la portada para comparar."""
    if bajar is None:
        from .proveedores.web import bajar
    from .proveedores import contactos
    dominio = contactos._base(dominio)
    try:
        html, ms = _bajar_medido(dominio, bajar)
    except Exception:                                    # noqa: BLE001
        # Sitios que sólo responden con www (mismo caso que contactos_de).
        try:
            html, ms = _bajar_medido("www." + dominio, bajar)
        except Exception:                                # noqa: BLE001
            return {"dominio": dominio, "error": "no_se_pudo_leer"}
    tecnica = {"https": True, "ms": ms, "kb": round(len(html.encode()) / 1024)}
    if completo:
        tecnica["robots"] = _existe(f"{dominio}/robots.txt", bajar, "user-agent")
        tecnica["sitemap"] = _existe(f"{dominio}/sitemap.xml", bajar, "<loc>")
    return {
        "dominio": dominio, "seo": seo_de_html(html), "medicion": medicion_de_html(html),
        "conversion": conversion_de_html(html), "tecnica": tecnica,
        "redes": contactos.redes_de_html(html, dominio),
    }


def _metricas_propias(dominio: str, redes: dict, bajar) -> dict:
    from . import redes_publicas
    from .modelos import Competidor
    yo = Competidor(dominio=dominio, nombre=dominio, posicionamiento="", redes=redes)
    redes_publicas.medir([yo], bajar=bajar)
    return yo.metricas


def cuota_de_voz(propias: dict, competidores: list[dict]) -> dict:
    """Seguidores propios sobre el total del mercado medido, por red. Sólo
    entran las cifras con estado «ok»: sumar un «no disponible» como cero
    inflaría la cuota de quien sí se pudo medir."""
    salida = {}
    for red in ("linkedin", "instagram", "facebook", "tiktok"):
        mio = (propias.get(red) or {})
        otros = [(c.get("metricas") or {}).get(red) or {} for c in competidores]
        cifras_otros = [o["seguidores"] for o in otros if o.get("estado") == "ok"]
        if mio.get("estado") != "ok" and not cifras_otros:
            continue
        propio = mio.get("seguidores") if mio.get("estado") == "ok" else None
        total = (propio or 0) + sum(cifras_otros)
        salida[red] = {"propios": propio, "competencia": sum(cifras_otros),
                       "competidores_medidos": len(cifras_otros),
                       "cuota": round(propio / total, 3) if propio is not None and total else None}
    return salida


def auditar(dominio: str, competidores: list[dict] | None = None, bajar=None) -> dict:
    """Todo junto: el sitio del cliente, sus redes con cifras públicas, la
    misma lectura rápida de cada competidor y los puntajes comparables."""
    competidores = (competidores or [])[:MAX_COMPETIDORES]
    with ThreadPoolExecutor(max_workers=1 + len(competidores)) as pool:
        propio_f = pool.submit(auditar_sitio, dominio, bajar, True)
        ajenos_f = [pool.submit(auditar_sitio, c.get("dominio", ""), bajar, False)
                    for c in competidores]
        propio = propio_f.result()
        ajenos = [f.result() for f in ajenos_f]
    if propio.get("error"):
        return {"dominio": propio["dominio"], "error": propio["error"], "pesos": PESOS}
    propio["metricas"] = _metricas_propias(propio["dominio"], propio["redes"], bajar)
    propio["puntajes"] = puntajes(propio)
    propio["recomendaciones"] = recomendaciones(propio)
    benchmark = []
    for c, a in zip(competidores, ajenos, strict=True):
        fila = {"dominio": a["dominio"], "nombre": c.get("nombre") or a["dominio"]}
        if not a.get("error"):
            a["metricas"] = c.get("metricas") or {}
            fila.update(puntaje=puntajes(a)["total"], medicion=a["medicion"],
                        conversion=a["conversion"], seo=_puntaje_seo(a["seo"]))
        else:
            fila["error"] = a["error"]
        benchmark.append(fila)
    propio.update(pesos=PESOS, benchmark=benchmark,
                  cuota_de_voz=cuota_de_voz(propio["metricas"], competidores),
                  fecha=time.strftime("%Y-%m-%d"))
    return propio
