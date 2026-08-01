"""
MV Cliente IA · generador de la landing en tres idiomas
=======================================================
Genera `landing/index.html` (es), `landing/pt/index.html` y
`landing/en/index.html` a partir de una sola plantilla y un diccionario de
textos. Es el mismo criterio que usa MV Kobra AI: **una** plantilla, tres
salidas, porque tres HTML editados a mano se desincronizan a la segunda
corrección.

    python3 -m marketing.generar_landing

Las tres páginas llevan el bloque completo de `hreflang` (las tres, no "las
otras dos"): un scraper social no ejecuta el selector de idioma, así que sin
esas etiquetas compartir /en/ mostraba la vista previa en español.
"""
from __future__ import annotations

import html
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "landing"
SITIO = "https://mvclienteia.com"

# --- textos ----------------------------------------------------------------
TEXTOS: dict[str, dict] = {
    "es": {
        "lang": "es", "locale": "es_UY", "ruta": "",
        "marca_html": 'MV CLIENTE <span class="gr">IA</span>',
        "marca": "MV Cliente IA",
        "titulo": "MV Cliente IA · Encontrá tus próximos clientes",
        "desc": "Pegá el enlace de tu producto: la IA investiga tu empresa, encuentra a tus "
                "compradores, ubica a los decisores y escribe los correos. Uruguay primero, "
                "después LATAM, después el mundo.",
        "nav": ["Cómo funciona", "Orden de mercado", "Video", "Idiomas", "Descargar"],
        "hero_k": "Prospección automática",
        "hero_h1": ["¿Sin clientes? Meses construyendo,", "todavía $0 de ingresos."],
        "hero_p": "El problema nunca fue el producto — eran las ventas. Pegá el enlace de tu "
                  "sitio, y el agente encuentra a tus compradores, escribe los correos y te deja "
                  "la lista priorizada. Vos aparecés y cerrás.",
        "hero_cta": "Probar con mi sitio",
        "hero_cta2": "Ver cómo funciona",
        "hero_nota": "Corre en tu navegador, en tu PC (Windows) y en tu celular (Android). "
                     "La demo usa datos sintéticos: se prueba sin entregar nada.",
        "pasos_h": "Seis pasos, uno detrás del otro",
        "pasos_p": "Es el mismo recorrido que haría un equipo de ventas en dos semanas — con "
                   "la diferencia de que acá termina antes de que te sirvas un café.",
        "pasos": [
            ("Investigá tu empresa", "Lee tu sitio y saca qué vendés, a quién y con qué argumento."),
            ("Explorá la competencia", "Contra quién te van a comparar y en qué se te parecen."),
            ("Definí campañas", "Un ángulo de mensaje por sector y por ola geográfica."),
            ("Encontrá clientes potenciales", "Empresas que encajan en tu perfil, con el motivo de por qué ahora."),
            ("Encontrá a los decisores", "Quién firma la decisión en cada una, con su cargo."),
            ("Escribí los correos", "Un primer contacto y su seguimiento, en el idioma de quien lo recibe."),
        ],
        "olas_h": "Uruguay primero. Después LATAM. Después el mundo.",
        "olas_p": "No es un filtro que se pone y se saca: el orden está adentro del puntaje. "
                  "Un prospecto uruguayo bueno siempre queda por delante de uno igual de bueno "
                  "de afuera, porque en Uruguay podés tocar la puerta.",
        "olas": [
            ("Uruguay", "Peso 1.00", "El mercado donde una reunión se consigue con una llamada."),
            ("LATAM", "Peso 0.72", "Argentina, Brasil, Chile, México y diez países más."),
            ("Resto del mundo", "Peso 0.45", "Donde el producto entra por el caso, no por la cercanía."),
        ],
        "video_h": "Noventa segundos, de punta a punta",
        "video_p": "Es el mismo video que va en los correos: cada país lo recibe en su idioma.",
        "video_falta": "El video todavía no está publicado. Poné tu archivo en "
                       "<code>landing/video/es/demo.mp4</code> y aparece acá.",
        "idiomas_h": "Tres idiomas, decididos por el país de quien recibe",
        "idiomas_p": "La interfaz la elegís vos. El correo no: sale en español, portugués o "
                     "inglés según el país del decisor. A Brasil se le escribe en portugués "
                     "aunque vos trabajes en español.",
        "desc_h": "Donde te quede cómodo",
        "desc_p": "El mismo producto, la misma interfaz, en los tres lados.",
        "desc_items": [
            ("Navegador", "Nada que instalar. Entrás y buscás."),
            ("PC · Windows", "Instalador propio. El motor corre en tu máquina, los datos no salen."),
            ("Android · APK", "La lista y los correos en el celular, apuntando a tu servidor."),
        ],
        "cierre_h": "Pegá tu enlace y mirá qué sale",
        "cierre_p": "La demo corre con datos sintéticos: no tenés que entregar nada para ver "
                    "cómo funciona el flujo completo.",
        "cierre_cta": "Empezar ahora",
        "pie": "Datos de demostración sintéticos. Las empresas y personas de la demo no son "
               "reales. Con el modo de investigación real, la información sale de fuentes "
               "públicas — revisala antes de contactar a nadie.",
    },
    "pt": {
        "lang": "pt-BR", "locale": "pt_BR", "ruta": "pt/",
        "marca_html": 'MV CLIENTE <span class="gr">IA</span>',
        "marca": "MV Cliente IA",
        "titulo": "MV Cliente IA · Encontre seus próximos clientes",
        "desc": "Cole o link do seu produto: a IA pesquisa sua empresa, encontra seus "
                "compradores, localiza os decisores e escreve os e-mails. Uruguai primeiro, "
                "depois LATAM, depois o mundo.",
        "nav": ["Como funciona", "Ordem de mercado", "Vídeo", "Idiomas", "Baixar"],
        "hero_k": "Prospecção automática",
        "hero_h1": ["Sem clientes? Meses construindo,", "e ainda R$0 de receita."],
        "hero_p": "O problema nunca foi o produto — eram as vendas. Cole o link do seu site e o "
                  "agente encontra seus compradores, escreve os e-mails e entrega a lista "
                  "priorizada. Você só aparece e fecha.",
        "hero_cta": "Testar com meu site",
        "hero_cta2": "Ver como funciona",
        "hero_nota": "Roda no navegador, no seu PC (Windows) e no celular (Android). "
                     "A demo usa dados sintéticos: dá para testar sem entregar nada.",
        "pasos_h": "Seis passos, um atrás do outro",
        "pasos_p": "É o mesmo caminho que um time de vendas faria em duas semanas — só que "
                   "aqui termina antes do seu café ficar pronto.",
        "pasos": [
            ("Pesquise sua empresa", "Lê seu site e extrai o que você vende, para quem e com qual argumento."),
            ("Explore a concorrência", "Com quem vão comparar você e no que vocês se parecem."),
            ("Defina campanhas", "Um ângulo de mensagem por setor e por onda geográfica."),
            ("Encontre clientes potenciais", "Empresas que se encaixam no seu perfil, com o motivo de por que agora."),
            ("Encontre os decisores", "Quem assina a decisão em cada uma, com o cargo."),
            ("Escreva os e-mails", "Um primeiro contato e seu follow-up, no idioma de quem recebe."),
        ],
        "olas_h": "Uruguai primeiro. Depois LATAM. Depois o mundo.",
        "olas_p": "Não é um filtro que se liga e desliga: a ordem está dentro da pontuação. "
                  "Um prospecto uruguaio bom sempre fica à frente de um igualmente bom de fora, "
                  "porque no Uruguai dá para bater na porta.",
        "olas": [
            ("Uruguai", "Peso 1,00", "O mercado onde uma reunião se consegue com um telefonema."),
            ("LATAM", "Peso 0,72", "Argentina, Brasil, Chile, México e mais dez países."),
            ("Resto do mundo", "Peso 0,45", "Onde o produto entra pelo caso, não pela proximidade."),
        ],
        "video_h": "Noventa segundos, de ponta a ponta",
        "video_p": "É o mesmo vídeo que vai nos e-mails: cada país recebe no seu idioma.",
        "video_falta": "O vídeo ainda não foi publicado. Coloque seu arquivo em "
                       "<code>landing/video/pt/demo.mp4</code> e ele aparece aqui.",
        "idiomas_h": "Três idiomas, definidos pelo país de quem recebe",
        "idiomas_p": "A interface você escolhe. O e-mail não: sai em espanhol, português ou "
                     "inglês conforme o país do decisor. Para o Brasil se escreve em português "
                     "mesmo que você trabalhe em espanhol.",
        "desc_h": "Onde for mais confortável",
        "desc_p": "O mesmo produto, a mesma interface, nos três lugares.",
        "desc_items": [
            ("Navegador", "Nada para instalar. Entra e busca."),
            ("PC · Windows", "Instalador próprio. O motor roda na sua máquina, os dados não saem."),
            ("Android · APK", "A lista e os e-mails no celular, apontando para o seu servidor."),
        ],
        "cierre_h": "Cole seu link e veja o que sai",
        "cierre_p": "A demo roda com dados sintéticos: você não precisa entregar nada para ver "
                    "o fluxo completo funcionando.",
        "cierre_cta": "Começar agora",
        "pie": "Dados de demonstração sintéticos. As empresas e pessoas da demo não são reais. "
               "No modo de pesquisa real, a informação vem de fontes públicas — revise antes "
               "de contatar alguém.",
    },
    "en": {
        "lang": "en", "locale": "en_US", "ruta": "en/",
        "marca_html": 'MV SearchCostumer <span class="gr">AI</span>',
        "marca": "MV SearchCostumer AI",
        "titulo": "MV SearchCostumer AI · Find your next customers",
        "desc": "Drop your product link: the AI researches your company, finds your buyers, "
                "locates the decision makers and writes the emails. Uruguay first, then LATAM, "
                "then the world.",
        "nav": ["How it works", "Market order", "Video", "Languages", "Download"],
        "hero_k": "Automatic prospecting",
        "hero_h1": ["No customers? Months building,", "still $0 in revenue."],
        "hero_p": "The problem was never the product — it was sales. Drop your website link and "
                  "the agent finds your buyers, writes the emails and hands you the prioritized "
                  "list. You just show up and close.",
        "hero_cta": "Try it with my site",
        "hero_cta2": "See how it works",
        "hero_nota": "Runs in your browser, on your PC (Windows) and on your phone (Android). "
                     "The demo uses synthetic data: evaluate it without handing anything over.",
        "pasos_h": "Six steps, one after another",
        "pasos_p": "It's the same path a sales team would walk in two weeks — except this one "
                   "finishes before your coffee does.",
        "pasos": [
            ("Research your company", "Reads your site and extracts what you sell, to whom, and with what argument."),
            ("Explore the competition", "Who you'll be compared against, and where you overlap."),
            ("Define campaigns", "One message angle per sector and per geographic wave."),
            ("Find potential customers", "Companies matching your profile, with the reason why now."),
            ("Find the decision makers", "Who signs off at each one, with their title."),
            ("Write the emails", "A first touch and its follow-up, in the recipient's language."),
        ],
        "olas_h": "Uruguay first. Then LATAM. Then the world.",
        "olas_p": "It isn't a filter you toggle: the ordering lives inside the score. A good "
                  "Uruguayan prospect always ranks ahead of an equally good one from abroad, "
                  "because in Uruguay you can knock on the door.",
        "olas": [
            ("Uruguay", "Weight 1.00", "The market where one phone call gets you a meeting."),
            ("LATAM", "Weight 0.72", "Argentina, Brazil, Chile, Mexico and ten more countries."),
            ("Rest of the world", "Weight 0.45", "Where the product wins on the case, not on proximity."),
        ],
        "video_h": "Ninety seconds, end to end",
        "video_p": "It's the same video the emails carry: each country gets it in its language.",
        "video_falta": "The video isn't published yet. Drop your file at "
                       "<code>landing/video/en/demo.mp4</code> and it shows up here.",
        "idiomas_h": "Three languages, decided by the recipient's country",
        "idiomas_p": "You pick the interface language. The email's isn't yours to pick: it goes "
                     "out in Spanish, Portuguese or English depending on the decision maker's "
                     "country. Brazil gets Portuguese even if you work in Spanish.",
        "desc_h": "Wherever suits you",
        "desc_p": "The same product and the same interface, in all three places.",
        "desc_items": [
            ("Browser", "Nothing to install. Open it and search."),
            ("PC · Windows", "Its own installer. The engine runs on your machine; data stays put."),
            ("Android · APK", "The list and the emails on your phone, pointing at your server."),
        ],
        "cierre_h": "Drop your link and see what comes out",
        "cierre_p": "The demo runs on synthetic data: you don't have to hand anything over to "
                    "see the whole flow work.",
        "cierre_cta": "Start now",
        "pie": "Synthetic demo data. The companies and people in the demo are not real. In real "
               "research mode the information comes from public sources — review it before "
               "contacting anyone.",
    },
}

# --- plantilla -------------------------------------------------------------
ESTILO = """
:root{
  --navy:#0a1020; --navy2:#0e1628; --navy3:#142036; --line:#24344f; --line2:#2a4160;
  --ink:#eaf1fb; --muted:#93a5c0; --faint:#7a8da7;
  --green:#00c896; --green2:#7cc242; --green-ink:#062018;
  --sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--navy);color:var(--ink);font-family:var(--sans);
  line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
h1,h2,h3{margin:0;line-height:1.12;letter-spacing:-.02em;text-wrap:balance}
.gr{color:var(--green)}

nav{position:sticky;top:0;z-index:30;background:rgba(10,16,32,.85);backdrop-filter:blur(10px);
  border-bottom:1px solid var(--line)}
nav .wrap{display:flex;align-items:center;gap:16px;height:62px}
.brand{display:flex;align-items:center;gap:10px;font-weight:800}
.brand img{width:30px;height:30px;border-radius:8px;display:block}
.brand b{font-size:15px}
.nlinks{display:flex;gap:2px;margin-left:12px}
.nlinks a{color:var(--muted);font-size:13.5px;font-weight:600;padding:7px 11px;border-radius:8px}
.nlinks a:hover{color:#fff;background:rgba(255,255,255,.06)}
@media(max-width:860px){.nlinks{display:none}}
.right{margin-left:auto;display:flex;align-items:center;gap:10px}
.lang{display:flex;gap:2px;background:rgba(255,255,255,.06);border:1px solid var(--line2);
  border-radius:8px;padding:3px}
.lang a{color:var(--faint);font-size:11.5px;font-weight:800;padding:5px 9px;border-radius:6px;
  letter-spacing:.03em}
.lang a.on{background:var(--green);color:var(--green-ink)}

.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;font-weight:750;
  font-size:14px;border-radius:9px;padding:11px 18px;border:1px solid transparent;
  transition:transform .12s}
.btn:hover{transform:translateY(-1px)}
.btn-a{background:var(--green);color:var(--green-ink);box-shadow:0 6px 20px rgba(0,200,150,.25)}
.btn-o{background:transparent;color:#fff;border-color:var(--line2)}
.btn-o:hover{border-color:var(--green);color:var(--green)}

.hero{padding:76px 0 64px;background:radial-gradient(1100px 460px at 50% -10%,
  rgba(0,200,150,.13),transparent 70%)}
.kicker{display:inline-block;font-size:11.5px;font-weight:800;letter-spacing:.09em;
  text-transform:uppercase;color:var(--green);border:1px solid rgba(0,200,150,.35);
  border-radius:20px;padding:5px 13px;margin-bottom:20px}
.hero h1{font-size:clamp(30px,5.4vw,52px);font-weight:850;max-width:19ch}
.hero h1 span{color:var(--muted)}
.hero p{color:var(--muted);font-size:17px;max-width:60ch;margin:20px 0 28px}
.acciones{display:flex;gap:12px;flex-wrap:wrap}
.hero small{display:block;color:var(--faint);font-size:13px;margin-top:20px;max-width:62ch}

section{padding:64px 0;border-top:1px solid var(--line)}
.sec-h{font-size:clamp(22px,3.2vw,32px);font-weight:800}
.sec-p{color:var(--muted);font-size:15.5px;max-width:66ch;margin:14px 0 34px}

.pasos{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px}
.paso{background:var(--navy2);border:1px solid var(--line);border-radius:14px;padding:20px 22px}
.paso .n{width:28px;height:28px;border-radius:50%;display:grid;place-items:center;
  background:var(--green);color:var(--green-ink);font-weight:800;font-size:13px;margin-bottom:12px}
.paso b{display:block;font-size:15px;margin-bottom:6px}
.paso p{margin:0;color:var(--muted);font-size:13.5px}

.olas{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}
.ola{background:var(--navy2);border:1px solid var(--line);border-radius:14px;padding:22px}
.ola.uno{border-color:rgba(0,200,150,.4)}
.ola b{display:block;font-size:17px;margin-bottom:4px}
.ola .peso{color:var(--green);font-weight:800;font-size:13px;font-variant-numeric:tabular-nums}
.ola p{margin:10px 0 0;color:var(--muted);font-size:13.5px}

.video-caja{background:var(--navy2);border:1px solid var(--line);border-radius:16px;
  padding:14px;max-width:820px}
.video-caja video{display:block;width:100%;border-radius:10px;background:#000}
.video-falta{color:var(--faint);font-size:13px;margin:12px 4px 4px}
.video-falta code{background:var(--navy3);border:1px solid var(--line);border-radius:6px;
  padding:2px 6px;font-size:12.5px}
.idiomas{display:flex;gap:10px;flex-wrap:wrap;margin-top:6px}
.chip{background:var(--navy3);border:1px solid var(--line);border-radius:20px;
  padding:8px 16px;font-size:13.5px;font-weight:700}
.chip i{font-style:normal;color:var(--green)}

.desc{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}
.d{background:var(--navy2);border:1px solid var(--line);border-radius:14px;padding:22px}
.d b{display:block;font-size:15px;margin-bottom:6px}
.d p{margin:0;color:var(--muted);font-size:13.5px}

.cierre{text-align:center;background:linear-gradient(180deg,transparent,rgba(0,200,150,.07))}
.cierre .sec-p{margin-left:auto;margin-right:auto}
footer{border-top:1px solid var(--line);padding:30px 0 46px;color:var(--faint);font-size:12.5px}
footer p{max-width:78ch;margin:0 0 10px}
"""


def _esc(t: str) -> str:
    return html.escape(t, quote=False)


def _alternates() -> str:
    filas = [f'<link rel="alternate" hreflang="{TEXTOS[i]["lang"]}" '
             f'href="{SITIO}/{TEXTOS[i]["ruta"]}">' for i in ("es", "pt", "en")]
    filas.append(f'<link rel="alternate" hreflang="x-default" href="{SITIO}/">')
    return "\n".join(filas)


def _selector(actual: str, base: str) -> str:
    etiquetas = {"es": "ES", "pt": "PT", "en": "EN"}
    partes = []
    for i in ("es", "pt", "en"):
        clase = ' class="on"' if i == actual else ""
        partes.append(f'<a href="{base}{TEXTOS[i]["ruta"]}"{clase}>{etiquetas[i]}</a>')
    return f'<div class="lang">{"".join(partes)}</div>'


def render(idioma: str) -> str:
    t = TEXTOS[idioma]
    # Desde /pt/ y /en/ los recursos y los otros idiomas viven un nivel arriba.
    base = "../" if t["ruta"] else ""
    app = f"{base}app/"

    pasos = "\n".join(
        f'<article class="paso"><div class="n">{i}</div><b>{_esc(n)}</b><p>{_esc(d)}</p></article>'
        for i, (n, d) in enumerate(t["pasos"], 1))
    olas = "\n".join(
        f'<article class="ola{" uno" if i == 0 else ""}"><b>{_esc(n)}</b>'
        f'<span class="peso">{_esc(p)}</span><p>{_esc(d)}</p></article>'
        for i, (n, p, d) in enumerate(t["olas"]))
    descargas = "\n".join(
        f'<article class="d"><b>{_esc(n)}</b><p>{_esc(d)}</p></article>'
        for n, d in t["desc_items"])
    enlaces = "".join(
        f'<a href="#{ancla}">{_esc(txt)}</a>'
        for ancla, txt in zip(("pasos", "olas", "video", "idiomas", "descargar"),
                              t["nav"], strict=True))

    # El aviso «todavía no está publicado» sólo tiene sentido mientras el
    # archivo no exista: dejarlo con el video andando confunde ("no tiene
    # video", dijo un usuario mirando la página con el video ya arriba).
    hay_video = (DESTINO / "video" / idioma / "demo.mp4").exists()
    aviso_video = "" if hay_video else f'<p class="video-falta">{t["video_falta"]}</p>'

    return f"""<!DOCTYPE html>
<html lang="{t['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(t['titulo'])}</title>
<meta name="description" content="{html.escape(t['desc'])}">
<link rel="icon" type="image/png" href="{base}mv_icon.png">
<link rel="canonical" href="{SITIO}/{t['ruta']}">
{_alternates()}
<meta property="og:type" content="website">
<meta property="og:site_name" content="{html.escape(t['marca'])}">
<meta property="og:locale" content="{t['locale']}">
<meta property="og:url" content="{SITIO}/{t['ruta']}">
<meta property="og:title" content="{html.escape(t['titulo'])}">
<meta property="og:description" content="{html.escape(t['desc'])}">
<meta name="twitter:card" content="summary_large_image">
<style>{ESTILO}</style>
</head>
<body>

<nav><div class="wrap">
  <a class="brand" href="{base}"><img src="{base}mv_icon.png" alt="{html.escape(t['marca'])}">
    <b>{t['marca_html']}</b></a>
  <div class="nlinks">{enlaces}</div>
  <div class="right">{_selector(idioma, base)}
    <a class="btn btn-a" href="{app}">{_esc(t['hero_cta'])}</a></div>
</div></nav>

<header class="hero"><div class="wrap">
  <span class="kicker">{_esc(t['hero_k'])}</span>
  <h1>{_esc(t['hero_h1'][0])}<br><span>{_esc(t['hero_h1'][1])}</span></h1>
  <p>{_esc(t['hero_p'])}</p>
  <div class="acciones">
    <a class="btn btn-a" href="{app}">{_esc(t['hero_cta'])} →</a>
    <a class="btn btn-o" href="#pasos">{_esc(t['hero_cta2'])}</a>
  </div>
  <small>{_esc(t['hero_nota'])}</small>
</div></header>

<section id="pasos"><div class="wrap">
  <h2 class="sec-h">{_esc(t['pasos_h'])}</h2>
  <p class="sec-p">{_esc(t['pasos_p'])}</p>
  <div class="pasos">{pasos}</div>
</div></section>

<section id="olas"><div class="wrap">
  <h2 class="sec-h">{_esc(t['olas_h'])}</h2>
  <p class="sec-p">{_esc(t['olas_p'])}</p>
  <div class="olas">{olas}</div>
</div></section>

<section id="video"><div class="wrap">
  <h2 class="sec-h">{_esc(t['video_h'])}</h2>
  <p class="sec-p">{_esc(t['video_p'])}</p>
  <div class="video-caja">
    <video controls preload="none" playsinline poster="{base}banners/banner_{idioma}.png">
      <source src="{base}video/{idioma}/demo.mp4" type="video/mp4">
    </video>
    {aviso_video}
  </div>
</div></section>

<section id="idiomas"><div class="wrap">
  <h2 class="sec-h">{_esc(t['idiomas_h'])}</h2>
  <p class="sec-p">{_esc(t['idiomas_p'])}</p>
  <div class="idiomas">
    <span class="chip"><i>ES</i> Español</span>
    <span class="chip"><i>PT</i> Português</span>
    <span class="chip"><i>EN</i> English</span>
  </div>
</div></section>

<section id="descargar"><div class="wrap">
  <h2 class="sec-h">{_esc(t['desc_h'])}</h2>
  <p class="sec-p">{_esc(t['desc_p'])}</p>
  <div class="desc">{descargas}</div>
</div></section>

<section class="cierre"><div class="wrap">
  <h2 class="sec-h">{_esc(t['cierre_h'])}</h2>
  <p class="sec-p">{_esc(t['cierre_p'])}</p>
  <a class="btn btn-a" href="{app}">{_esc(t['cierre_cta'])} →</a>
</div></section>

<footer><div class="wrap"><p>{_esc(t['pie'])}</p><p>© {_esc(t['marca'])}</p></div></footer>

</body>
</html>
"""


def generar() -> list[Path]:
    salidas: list[Path] = []
    for idioma, t in TEXTOS.items():
        destino = DESTINO / t["ruta"] / "index.html"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(render(idioma), encoding="utf-8")
        salidas.append(destino)
    return salidas


if __name__ == "__main__":
    for p in generar():
        print(f"  ✓ {p.relative_to(RAIZ)}  ({p.stat().st_size // 1024} KB)")
