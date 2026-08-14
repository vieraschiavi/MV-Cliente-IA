"""
MV Cliente IA · enlaces del mensaje (sitio, video, banner)
==========================================================
Cada correo y cada mensaje de LinkedIn lleva tres cosas además del texto
personalizado: el **banner** de marca, el **video** y el **enlace a la web** —
las tres **en el idioma del país de quien recibe**, no en el del que escribe.

Las URLs se derivan del dominio del producto siguiendo la convención de tres
idiomas de MV Kobra AI (`/` español, `/pt/`, `/en/`), y se pueden pisar una
por una desde la API o la línea de comandos, porque el video de verdad puede
estar en YouTube, en Vimeo o en un CDN, no necesariamente en el propio sitio.

> El producto arma el enlace; **los archivos de video los ponés vos**. Si no
> hay video todavía, se corre con `videos={}` y ni el correo ni el mensaje de
> LinkedIn mencionan ninguno — no se promete un video que no existe.

Los enlaces salen etiquetados con UTM para que después se pueda ver qué
campaña, qué idioma y qué empresa trajeron la visita.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from urllib.parse import quote, urlencode, urlsplit

from . import geo, metricas

# Ruta de cada idioma dentro del sitio (la convención de Kobra).
RUTA_IDIOMA = {"es": "", "pt": "pt/", "en": "en/"}

# Dónde quedan los banners que genera `marketing/generar_banners.py`.
RUTA_BANNER = "landing/banners/banner_{idioma}.png"

# Ancla de la sección de video de la landing generada.
ANCLA_VIDEO = "#video"


def _normalizar_sitio(dominio_o_url: str) -> str:
    d = (dominio_o_url or "").strip().rstrip("/")
    if not d:
        return ""
    if not d.startswith(("http://", "https://")):
        d = "https://" + d
    return d


def _url_navegable(u: str) -> str:
    """La URL si es http/https; cadena vacía si no.

    El video y el banner los escribe quien lanza la corrida, y de ahí van
    derecho al `href` del correo HTML y de la pantalla de Correos. `escape()`
    de la redacción tapa las comillas pero no el ESQUEMA: un
    `javascript:fetch(...)` pasaba entero hasta el enlace. Un enlace de
    correo sólo puede ser http o https —ningún cliente de correo abre otra
    cosa— así que descartar el resto no le quita nada al producto.
    """
    u = (u or "").strip()
    if not u:
        return ""
    # `\` y espacios de control confunden a los parsers de URL de algunos
    # navegadores: si algo así llega, no es un enlace legítimo.
    if any(c in u for c in "\\\r\n\t") or not re.match(r"(?i)^https?://[^\s/]", u):
        return ""
    return u


@dataclass
class Enlaces:
    """
    Los enlaces de una corrida. `videos` y `banners` son mapas idioma → URL;
    lo que no esté en el mapa se deriva del sitio.
    """
    sitio: str = ""
    videos: dict[str, str] = field(default_factory=dict)
    banners: dict[str, str] = field(default_factory=dict)
    # Con `videos` vacío y esto en False, los mensajes no hablan de ningún
    # video. Se enciende solo cuando hay al menos un video declarado o cuando
    # se pide explícitamente usar la sección de video de la landing.
    video_en_landing: bool = False
    utm: bool = True

    @classmethod
    def desde_dominio(cls, dominio: str, **kw) -> Enlaces:
        return cls(sitio=_normalizar_sitio(dominio), **kw)

    # ------------------------------------------------------------------
    def _idioma(self, idioma: str) -> str:
        return idioma if idioma in RUTA_IDIOMA else geo.IDIOMA_DEFAULT

    def landing(self, idioma: str, campana_id: str = "", prospecto_id: str = "",
                canal: str = "email") -> str:
        """URL de la landing en el idioma del receptor, con UTM."""
        if not self.sitio:
            return ""
        base = f"{self.sitio}/{RUTA_IDIOMA[self._idioma(idioma)]}"
        return base + self._utm(canal, idioma, campana_id, prospecto_id)

    def video(self, idioma: str, campana_id: str = "", prospecto_id: str = "",
              canal: str = "email") -> str:
        """
        URL del video en el idioma del receptor. Cadena vacía si no hay video
        declarado y no se pidió usar el de la landing — es lo que hace que el
        mensaje simplemente no lo mencione.
        """
        idi = self._idioma(idioma)
        propio = self.videos.get(idi) or self.videos.get(geo.IDIOMA_DEFAULT)
        if propio:
            # Un video externo (YouTube, Vimeo, un CDN) se deja tal cual: no
            # todos aceptan parámetros extra sin romper la reproducción.
            return propio
        if not (self.video_en_landing and self.sitio):
            return ""
        base = f"{self.sitio}/{RUTA_IDIOMA[idi]}"
        return base + self._utm(canal, idi, campana_id, prospecto_id) + ANCLA_VIDEO

    def banner(self, idioma: str) -> str:
        idi = self._idioma(idioma)
        propio = self.banners.get(idi)
        if propio:
            return propio
        if not self.sitio:
            return ""
        return f"{self.sitio}/{RUTA_BANNER.format(idioma=idi)}"

    def hay_video(self, idioma: str) -> bool:
        return bool(self.video(idioma))

    # ------------------------------------------------------------------
    def traqueada(self, url: str, meta: dict) -> str:
        """El enlace que va al correo, envuelto por el redirect de conversión
        `/api/ir` — así un click queda atribuido al segmento/canal/día.

        Opt-in y sin efecto salvo que estén las DOS cosas: la URL pública del
        redirect (`MVCLIENTE_URL_TRAQUEO`) y el secreto de firma. Sin eso, el
        enlace sale directo como siempre — la función de métricas de
        conversión se enciende poniendo esas dos variables, no por default.
        """
        base = (os.getenv("MVCLIENTE_URL_TRAQUEO") or "").strip()
        if not url or not base or not metricas.hay_traqueo():
            return url
        if not url.startswith(("http://", "https://")):
            return url
        completa = {"programa": self._host(), **{k: v for k, v in meta.items() if v}}
        return metricas.url_de_traqueo(base, url, completa)

    def _host(self) -> str:
        """El dominio del producto, que es la clave con la que se agrupan las
        métricas por programa."""
        try:
            return (urlsplit(self.sitio).hostname or "").lower()
        except ValueError:
            return ""

    # ------------------------------------------------------------------
    def _utm(self, canal: str, idioma: str, campana_id: str, prospecto_id: str) -> str:
        if not self.utm:
            return ""
        params = {
            "utm_source": canal,              # email · linkedin
            "utm_medium": "outbound",
            "utm_campaign": campana_id or "autogtm",
            "utm_term": idioma,               # sirve para ver qué idioma convierte
        }
        if prospecto_id:
            params["utm_content"] = prospecto_id
        return "?" + urlencode(params, quote_via=quote)

    def a_dict(self) -> dict:
        return {"sitio": self.sitio, "videos": dict(self.videos),
                "banners": dict(self.banners),
                "video_en_landing": self.video_en_landing, "utm": self.utm}


def desde_dict(d: dict | None, dominio: str = "") -> Enlaces:
    """Reconstruye la configuración; sin datos, la deriva del dominio."""
    if not d:
        return Enlaces.desde_dominio(dominio)
    # Los videos y banners se filtran acá, en el borde: es el único punto por
    # el que entran URLs escritas a mano, y de acá salen directo al `href` de
    # cada correo.
    return Enlaces(
        sitio=_normalizar_sitio(d.get("sitio") or dominio),
        videos={k: _url_navegable(v) for k, v in (d.get("videos") or {}).items()
                if _url_navegable(v)},
        banners={k: _url_navegable(v) for k, v in (d.get("banners") or {}).items()
                 if _url_navegable(v)},
        video_en_landing=bool(d.get("video_en_landing")),
        utm=bool(d.get("utm", True)),
    )
