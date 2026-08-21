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

# La landing YA NO enlaza descargas. Acá vivían las URLs de la Release —el
# instalador de Windows, el portable, la edición BAT y el APK, todos en su
# variante demo— y bastaba con abrir la página para llevarse el producto
# entero sin dejar ni un nombre: la demo pública regalaba el artefacto de
# ingeniería, no el resultado. Los binarios se siguen publicando en la Release
# (los arman build_windows.yml y apk.yml, cada uno con su .sha256) porque son
# el canal de entrega de quien compra la licencia; lo que cambió es que ya no
# se ofrecen a cualquiera que pase. El visitante prueba la app en el navegador
# —con datos sintéticos, sin instalar nada— y para ver el producto completo
# pide una demo uno a uno por el formulario de #demo.
#
# Sentinela: en render() se reemplaza por la ruta relativa a /app/.
APP = "@APP@"

# --- textos ----------------------------------------------------------------
TEXTOS: dict[str, dict] = {
    "es": {
        "lang": "es", "locale": "es_UY", "ruta": "",
        "marca_html": 'MV CLIENTE <span class="gr">IA</span>',
        "marca": "MV Cliente IA",
        "titulo": "MV Cliente IA · Encontrá tus próximos clientes",
        "desc": "Pegá el enlace de tu producto: la IA investiga tu empresa, encuentra a tus "
                "compradores, ubica a los decisores y escribe los correos.",
        "nav": ["Cómo funciona", "Video", "Idiomas", "Probar", "Demo", "Precios"],
        "hero_k": "Prospección automática, 24/7",
        "hero_h1": ["¿Sin clientes? Meses construyendo,", "todavía $0 de ingresos."],
        "hero_p": "El problema nunca fue el producto — eran las ventas. Pegá el enlace de tu "
                  "sitio, y el agente investiga el mercado, encuentra a tus compradores, escribe "
                  "los correos y te deja la lista priorizada — en un minuto, en piloto "
                  "automático, incluso mientras dormís. Vos aparecés y cerrás.",
        "hero_cta": "Probar con mi sitio",
        "hero_cta2": "Ver cómo funciona",
        "hero_nota": "Probalo ahora mismo en el navegador, con datos sintéticos y sin "
                     "entregar nada. Las versiones de PC (Windows) y Android vienen con la "
                     "licencia; el producto completo se muestra en una demo uno a uno.",
        "pasos_h": "Seis pasos, uno detrás del otro",
        "pasos_p": "Es el mismo recorrido que haría un equipo de ventas en dos semanas — con "
                   "la diferencia de que acá termina antes de que te sirvas un café.",
        "pasos": [
            ("Investigá tu empresa", "Lee tu sitio y saca qué vendés, a quién y con qué argumento."),
            ("Explorá la competencia", "Contra quién te van a comparar y en qué se te parecen."),
            ("Definí campañas", "Un ángulo de mensaje por sector y por mercado."),
            ("Encontrá clientes potenciales", "Empresas que encajan en tu perfil, con el motivo de por qué ahora."),
            ("Encontrá a los decisores", "Quién firma la decisión en cada una, con su cargo."),
            ("Escribí los correos", "Un primer contacto y su seguimiento, en el idioma de quien lo recibe."),
        ],
        "video_h": "Miralo funcionando, de punta a punta",
        "video_p": "Es el mismo video que va en los correos: cada país lo recibe en su idioma.",
        "video_falta": "El video todavía no está publicado. Poné tu archivo en "
                       "<code>landing/video/es/demo.mp4</code> y aparece acá.",
        "idiomas_h": "Tres idiomas, decididos por el país de quien recibe",
        "idiomas_p": "La interfaz la elegís vos. El correo no: sale en español, portugués o "
                     "inglés según el país del decisor. A Brasil se le escribe en portugués "
                     "aunque vos trabajes en español.",
        "desc_h": "Probalo en el navegador",
        "desc_p": "La misma interfaz que en PC y en Android, corriendo acá mismo.",
        "desc_items": [
            ("Navegador", "Nada que instalar. Entrás y ves cómo trabaja el agente.",
             "Abrir la app", APP,
             "La misma interfaz que en PC y Android. Para ver el producto completo "
             "—instalado, con tus datos y sin límite— pedí una demo por acá abajo."),
        ],
        "demo_h": "La demo completa se muestra en vivo",
        "demo_p": "El programa instalado —PC y Android, con tus datos y sin límite— no se "
                  "descarga desde acá: te lo mostramos en una reunión de 30 minutos, uno a "
                  "uno, con tu propio sitio como ejemplo. Dejá tus datos y coordinamos.",
        "demo_nombre": "Nombre completo",
        "demo_empresa": "Empresa",
        "demo_pais": "País",
        "demo_email": "Correo de trabajo",
        "demo_mensaje": "Qué vendés y a quién (opcional)",
        "demo_cta": "Pedir la demo",
        "demo_enviando": "Enviando…",
        "demo_ok": "Pedido recibido. Te escribimos a tu correo para coordinar el horario.",
        "demo_agenda": "Agendar ahora",
        "demo_manual": "No pudimos enviar el aviso automático. Escribinos directo a",
        "demo_error": "No se pudo enviar el pedido. Probá de nuevo o escribinos a "
                      "vieraschiavi@gmail.com.",
        "demo_nota": "Usamos tus datos sólo para coordinar la demo. No los compartimos con "
                     "nadie y no te suscribimos a nada.",
        "precios_h": "Precios",
        "precios_p": "La web es la prueba: demo sintética ilimitada y 3 búsquedas reales gratis "
                     "por visitante, con tu propia clave de IA (Claude, ChatGPT, Gemini o "
                     "Copilot). El programa completo se paga "
                     "una sola vez.",
        "plan_gratis_t": "Web gratis",
        "plan_gratis": ["Demo sintética ilimitada",
                        "3 búsquedas reales gratis (con tu clave de Claude, ChatGPT, Gemini o Copilot)",
                        "Los tres idiomas y el export CSV/Excel"],
        "plan_gratis_cta": "Probar ahora",
        "plan_pago_t": "Licencia completa · PC + Android",
        "plan_pago_precio": "US$ 149",
        "plan_pago_nota": "pago único · ≈ $U 6.000 · se cobra en pesos por MercadoPago",
        "plan_pago": ["Instalador de Windows + versión portable",
                      "APK de Android",
                      "Búsquedas sin límite, con tus propias claves",
                      "Actualizaciones incluidas"],
        "plan_pago_cta": "Comprar con MercadoPago",
        "plan_pago_error": "No se pudo iniciar el pago. Probá de nuevo en un rato o escribinos a vieraschiavi@gmail.com.",
        "pago_ok_h": "¡Listo! Tu licencia está activa",
        "pago_ok_p": "Esta es tu clave. Copiala y pegala en Configuración → «Clave de licencia», tanto en la app de PC como en el celular. Guardala: te la volvemos a mostrar si entrás de nuevo con el mismo enlace de pago.",
        "pago_ok_copiar": "Copiar clave",
        "pago_ok_copiado": "Copiada",
        "pago_error": "No pudimos confirmar el pago todavía. Si MercadoPago ya te lo aprobó, esperá un minuto y recargá esta página. Si sigue igual, escribinos a vieraschiavi@gmail.com con el número de pago.",
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
                "compradores, localiza os decisores e escreve os e-mails.",
        "nav": ["Como funciona", "Vídeo", "Idiomas", "Testar", "Demo", "Preços"],
        "hero_k": "Prospecção automática, 24/7",
        "hero_h1": ["Sem clientes? Meses construindo,", "e ainda R$0 de receita."],
        "hero_p": "O problema nunca foi o produto — eram as vendas. Cole o link do seu site e o "
                  "agente pesquisa o mercado, encontra seus compradores, escreve os e-mails e "
                  "entrega a lista priorizada — em um minuto, no piloto automático, até "
                  "enquanto você dorme. Você só aparece e fecha.",
        "hero_cta": "Testar com meu site",
        "hero_cta2": "Ver como funciona",
        "hero_nota": "Teste agora mesmo no navegador, com dados sintéticos e sem entregar "
                     "nada. As versões de PC (Windows) e Android vêm com a licença; o produto "
                     "completo é mostrado numa demo um a um.",
        "pasos_h": "Seis passos, um atrás do outro",
        "pasos_p": "É o mesmo caminho que um time de vendas faria em duas semanas — só que "
                   "aqui termina antes do seu café ficar pronto.",
        "pasos": [
            ("Pesquise sua empresa", "Lê seu site e extrai o que você vende, para quem e com qual argumento."),
            ("Explore a concorrência", "Com quem vão comparar você e no que vocês se parecem."),
            ("Defina campanhas", "Um ângulo de mensagem por setor e por mercado."),
            ("Encontre clientes potenciais", "Empresas que se encaixam no seu perfil, com o motivo de por que agora."),
            ("Encontre os decisores", "Quem assina a decisão em cada uma, com o cargo."),
            ("Escreva os e-mails", "Um primeiro contato e seu follow-up, no idioma de quem recebe."),
        ],
        "video_h": "Veja funcionando, de ponta a ponta",
        "video_p": "É o mesmo vídeo que vai nos e-mails: cada país recebe no seu idioma.",
        "video_falta": "O vídeo ainda não foi publicado. Coloque seu arquivo em "
                       "<code>landing/video/pt/demo.mp4</code> e ele aparece aqui.",
        "idiomas_h": "Três idiomas, definidos pelo país de quem recebe",
        "idiomas_p": "A interface você escolhe. O e-mail não: sai em espanhol, português ou "
                     "inglês conforme o país do decisor. Para o Brasil se escreve em português "
                     "mesmo que você trabalhe em espanhol.",
        "desc_h": "Teste no navegador",
        "desc_p": "A mesma interface do PC e do Android, rodando aqui mesmo.",
        "desc_items": [
            ("Navegador", "Nada para instalar. Entra e vê como o agente trabalha.",
             "Abrir o app", APP,
             "A mesma interface do PC e do Android. Para ver o produto completo "
             "—instalado, com seus dados e sem limite— peça uma demo aqui embaixo."),
        ],
        "demo_h": "A demo completa é apresentada ao vivo",
        "demo_p": "O programa instalado —PC e Android, com seus dados e sem limite— não é "
                  "baixado daqui: mostramos numa reunião de 30 minutos, um a um, usando o seu "
                  "próprio site como exemplo. Deixe seus dados e combinamos o horário.",
        "demo_nombre": "Nome completo",
        "demo_empresa": "Empresa",
        "demo_pais": "País",
        "demo_email": "E-mail de trabalho",
        "demo_mensaje": "O que você vende e para quem (opcional)",
        "demo_cta": "Pedir a demo",
        "demo_enviando": "Enviando…",
        "demo_ok": "Pedido recebido. Escrevemos para o seu e-mail para combinar o horário.",
        "demo_agenda": "Agendar agora",
        "demo_manual": "Não conseguimos enviar o aviso automático. Escreva direto para",
        "demo_error": "Não foi possível enviar o pedido. Tente de novo ou escreva para "
                      "vieraschiavi@gmail.com.",
        "demo_nota": "Usamos seus dados só para combinar a demo. Não compartilhamos com "
                     "ninguém e não inscrevemos você em nada.",
        "precios_h": "Preços",
        "precios_p": "A web é o teste: demo sintética ilimitada e 3 buscas reais grátis por "
                     "visitante, com a sua própria chave de IA (Claude, ChatGPT, Gemini ou "
                     "Copilot). O programa completo se paga "
                     "uma única vez.",
        "plan_gratis_t": "Web grátis",
        "plan_gratis": ["Demo sintética ilimitada",
                        "3 buscas reais grátis (com a sua chave do Claude, ChatGPT, Gemini ou Copilot)",
                        "Os três idiomas e o export CSV/Excel"],
        "plan_gratis_cta": "Testar agora",
        "plan_pago_t": "Licença completa · PC + Android",
        "plan_pago_precio": "US$ 149",
        "plan_pago_nota": "pagamento único · ≈ $U 6.000 · cobrado em pesos via MercadoPago",
        "plan_pago": ["Instalador do Windows + versão portátil",
                      "APK do Android",
                      "Buscas sem limite, com as suas próprias chaves",
                      "Atualizações incluídas"],
        "plan_pago_cta": "Comprar com MercadoPago",
        "plan_pago_error": "Não foi possível iniciar o pagamento. Tente de novo em instantes ou escreva para vieraschiavi@gmail.com.",
        "pago_ok_h": "Pronto! Sua licença está ativa",
        "pago_ok_p": "Esta é a sua chave. Copie e cole em Configurações → «Chave de licença», tanto no app de PC quanto no celular. Guarde-a: mostramos de novo se você voltar pelo mesmo link de pagamento.",
        "pago_ok_copiar": "Copiar chave",
        "pago_ok_copiado": "Copiada",
        "pago_error": "Ainda não conseguimos confirmar o pagamento. Se o MercadoPago já aprovou, espere um minuto e recarregue esta página. Se continuar, escreva para vieraschiavi@gmail.com com o número do pagamento.",
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
                "locates the decision makers and writes the emails.",
        "nav": ["How it works", "Video", "Languages", "Try it", "Demo", "Pricing"],
        "hero_k": "Automatic prospecting, 24/7",
        "hero_h1": ["No customers? Months building,", "still $0 in revenue."],
        "hero_p": "The problem was never the product — it was sales. Drop your website link and "
                  "the agent researches the market, finds your buyers, writes the emails and "
                  "hands you the prioritized list — in a minute, on autopilot, even while you "
                  "sleep. You just show up and close.",
        "hero_cta": "Try it with my site",
        "hero_cta2": "See how it works",
        "hero_nota": "Try it right now in your browser, on synthetic data, without handing "
                     "anything over. The PC (Windows) and Android builds come with the "
                     "licence; the full product is shown in a one-to-one demo.",
        "pasos_h": "Six steps, one after another",
        "pasos_p": "It's the same path a sales team would walk in two weeks — except this one "
                   "finishes before your coffee does.",
        "pasos": [
            ("Research your company", "Reads your site and extracts what you sell, to whom, and with what argument."),
            ("Explore the competition", "Who you'll be compared against, and where you overlap."),
            ("Define campaigns", "One message angle per sector and per market."),
            ("Find potential customers", "Companies matching your profile, with the reason why now."),
            ("Find the decision makers", "Who signs off at each one, with their title."),
            ("Write the emails", "A first touch and its follow-up, in the recipient's language."),
        ],
        "video_h": "See it running, end to end",
        "video_p": "It's the same video the emails carry: each country gets it in its language.",
        "video_falta": "The video isn't published yet. Drop your file at "
                       "<code>landing/video/en/demo.mp4</code> and it shows up here.",
        "idiomas_h": "Three languages, decided by the recipient's country",
        "idiomas_p": "You pick the interface language. The email's isn't yours to pick: it goes "
                     "out in Spanish, Portuguese or English depending on the decision maker's "
                     "country. Brazil gets Portuguese even if you work in Spanish.",
        "desc_h": "Try it in your browser",
        "desc_p": "The same interface as on desktop and Android, running right here.",
        "desc_items": [
            ("Browser", "Nothing to install. Open it and watch the agent work.",
             "Open the app", APP,
             "The same interface as on desktop and Android. To see the full product "
             "—installed, with your data and no limits— request a demo below."),
        ],
        "demo_h": "The full demo is shown live",
        "demo_p": "The installed program —desktop and Android, on your data with no limits— "
                  "isn't downloadable from here: we walk you through it in a 30-minute "
                  "one-to-one call, using your own site as the example. Leave your details "
                  "and we'll set up a time.",
        "demo_nombre": "Full name",
        "demo_empresa": "Company",
        "demo_pais": "Country",
        "demo_email": "Work email",
        "demo_mensaje": "What you sell and to whom (optional)",
        "demo_cta": "Request the demo",
        "demo_enviando": "Sending…",
        "demo_ok": "Request received. We'll email you to set up a time.",
        "demo_agenda": "Book a time now",
        "demo_manual": "We couldn't send the automatic notice. Write to us directly at",
        "demo_error": "The request couldn't be sent. Try again or write to "
                      "vieraschiavi@gmail.com.",
        "demo_nota": "We use your details only to set up the demo. We don't share them with "
                     "anyone and we don't subscribe you to anything.",
        "precios_h": "Pricing",
        "precios_p": "The web is the trial: unlimited synthetic demo and 3 free real searches "
                     "per visitor, with your own AI key (Claude, ChatGPT, Gemini or Copilot). "
                     "The full program is a one-time "
                     "purchase.",
        "plan_gratis_t": "Free web",
        "plan_gratis": ["Unlimited synthetic demo",
                        "3 free real searches (with your Claude, ChatGPT, Gemini or Copilot key)",
                        "All three languages plus CSV/Excel export"],
        "plan_gratis_cta": "Try it now",
        "plan_pago_t": "Full license · PC + Android",
        "plan_pago_precio": "US$ 149",
        "plan_pago_nota": "one-time payment · ≈ $U 6,000 · charged in Uruguayan pesos via MercadoPago",
        "plan_pago": ["Windows installer + portable edition",
                      "Android APK",
                      "Unlimited searches, with your own keys",
                      "Updates included"],
        "plan_pago_cta": "Buy with MercadoPago",
        "plan_pago_error": "Could not start the payment. Try again in a bit or write to vieraschiavi@gmail.com.",
        "pago_ok_h": "Done! Your license is active",
        "pago_ok_p": "This is your key. Copy it and paste it into Settings → “License key”, both in the desktop app and on your phone. Keep it: we show it again if you come back through the same payment link.",
        "pago_ok_copiar": "Copy key",
        "pago_ok_copiado": "Copied",
        "pago_error": "We could not confirm the payment yet. If MercadoPago already approved it, wait a minute and reload this page. If it persists, write to vieraschiavi@gmail.com with the payment number.",
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
nav .wrap{display:flex;align-items:center;gap:12px;height:62px;padding:0 16px}
.brand{display:flex;align-items:center;gap:10px;font-weight:800;flex:none;white-space:nowrap}
.brand img{width:30px;height:30px;border-radius:8px;display:block}
.brand b{font-size:15px}
.nlinks{display:flex;gap:2px;margin-left:8px}
.nlinks a{color:var(--muted);font-size:13.5px;font-weight:600;padding:7px 8px;border-radius:8px;
  white-space:nowrap}
.nlinks a:hover{color:#fff;background:rgba(255,255,255,.06)}
/* La barra tiene alto fijo (62px) y no envuelve: si los enlaces no entran,
   se esconden enteros en vez de partirse en dos líneas. Pasó al agregar
   «Pedir demo»: con seis enlaces, «Cómo funciona» se cortaba en dos y el
   botón verde se salía de la pantalla. Seis enlaces entran justo en los
   1032px útiles de .wrap, así que abajo de 1080 se ocultan (el contenido
   sigue a un scroll de distancia). */
@media(max-width:1080px){.nlinks{display:none}}
.right{margin-left:auto;display:flex;align-items:center;gap:8px;flex:none}
nav .right .btn{padding:10px 14px}
/* En un celular no entran el nombre largo del producto, el selector de idioma
   y un botón de cuatro palabras: el botón pasa a la etiqueta corta (la misma
   del menú) y el nombre se queda en el isotipo. Sin esto la barra medía 519px
   en una pantalla de 320 y arrastraba scroll horizontal a TODA la página. */
.cta-corto{display:none}
@media(max-width:640px){.cta-largo{display:none}.cta-corto{display:inline}}
@media(max-width:430px){.brand b{display:none}}
.lang{display:flex;gap:2px;background:rgba(255,255,255,.06);border:1px solid var(--line2);
  border-radius:8px;padding:3px}
.lang a{color:var(--faint);font-size:11.5px;font-weight:800;padding:5px 9px;border-radius:6px;
  letter-spacing:.03em}
.lang a.on{background:var(--green);color:var(--green-ink)}

.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;font-weight:750;
  font-size:14px;border-radius:9px;padding:11px 18px;border:1px solid transparent;
  transition:transform .12s;white-space:nowrap}
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
.d .btn{display:inline-flex;margin-top:14px}
.btn .ico{flex:none}
.d small{display:block;margin-top:10px;color:var(--faint);font-size:12px;line-height:1.5}

.planes{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px;max-width:820px}
.plan{background:var(--navy2);border:1px solid var(--line);border-radius:14px;padding:24px}
.plan.destacado{border-color:var(--green)}
.plan b{display:block;font-size:15px;margin-bottom:10px}
.plan .precio{font-size:34px;font-weight:800;letter-spacing:-.5px}
.plan .precio-nota{display:block;color:var(--faint);font-size:12px;margin:4px 0 12px}
/* `hidden` lo aplica el navegador con `display:none`, pero CUALQUIER regla de
   autor con `display` le gana — y `.btn` pone `inline-flex`. Sin esto, el
   botón «copiar clave» seguía a la vista después de un pago rechazado,
   ofreciendo copiar una clave que no existe. Lo encontró la prueba en
   navegador, no la lectura del código. */
[hidden]{display:none !important}
/* La clave que se entrega al volver del pago. `word-break` porque son ~120
   caracteres sin espacios y en un celular se sale de la pantalla. */
.pago-vuelta{margin:28px auto 0;max-width:640px;padding:20px 22px;border-radius:14px;
  border:1px solid var(--green-deep);background:rgba(92,181,49,.08);text-align:left}
.pago-vuelta h3{margin:0 0 8px;font-size:19px}
.pago-vuelta p{margin:0 0 14px;color:var(--faint);font-size:14px;line-height:1.55}
.pago-vuelta code{display:block;padding:12px 14px;border-radius:10px;background:#0b1220;
  color:#e8eef7;font-size:13px;word-break:break-all;margin-bottom:14px;user-select:all}
.pago-vuelta code.pago-falla{background:transparent;color:var(--amber);padding:0;user-select:auto}
.plan ul{margin:0 0 16px;padding-left:18px;color:var(--muted);font-size:13.5px}
.plan li{margin-bottom:6px}

/* Pedido de demo. El producto instalado no se descarga de acá: se muestra en
   una reunión. Un .exe público es el artefacto de ingeniería entero servido a
   quien quiera copiarlo, y no deja rastro de quién se lo llevó. */
.demo-form{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;
  max-width:760px;background:var(--navy2);border:1px solid var(--line);border-radius:16px;
  padding:24px}
.demo-form label{display:block;font-size:12.5px;font-weight:700;color:var(--muted);
  margin-bottom:6px}
.demo-form input,.demo-form textarea{width:100%;box-sizing:border-box;background:var(--navy3);
  border:1px solid var(--line2);border-radius:10px;padding:11px 13px;color:#fff;
  font:inherit;font-size:14px}
.demo-form input:focus,.demo-form textarea:focus{outline:none;border-color:var(--green)}
.demo-form textarea{min-height:88px;resize:vertical}
.demo-ancho{grid-column:1/-1}
.demo-form .btn{justify-self:start}
.demo-nota{color:var(--faint);font-size:12.5px;line-height:1.55;margin:0}
.demo-estado{margin:0;font-size:14px;line-height:1.55;color:var(--green)}
.demo-estado.mal{color:var(--amber)}
.demo-estado a{color:inherit;text-decoration:underline}

.cierre{text-align:center;background:linear-gradient(180deg,transparent,rgba(0,200,150,.07))}
.cierre .sec-p{margin-left:auto;margin-right:auto}
footer{border-top:1px solid var(--line);padding:30px 0 46px;color:var(--faint);font-size:12.5px}
footer p{max-width:78ch;margin:0 0 10px}
"""


def _esc(t: str) -> str:
    return html.escape(t, quote=False)


# Los mismos trazos que webapp/frontend/src/componentes/Iconos.jsx, en línea:
# la landing es un HTML suelto que se sirve estático, así que no puede pedirle
# una fuente de iconos a nadie. Antes acá había un emoji (⬇) y en cada sistema
# operativo salía de otro color, al lado de un botón de la paleta Kobra.
_TRAZOS = {
    "flecha": '<path d="M4.4 12h15.2"/><path d="m13.6 5.6 6.4 6.4-6.4 6.4"/>',
}


def _ico(nombre: str) -> str:
    """SVG decorativo: el texto del botón es el que nombra la acción."""
    return (f'<svg class="ico" viewBox="0 0 24 24" width="17" height="17" fill="none" '
            f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true" focusable="false">'
            f'{_TRAZOS[nombre]}</svg>')


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
    def _tarjeta_descarga(n, d, cta, href, nota):
        # `href` sólo puede ser el sentinela APP: acá ya no se enlazan binarios
        # (ver el comentario de APP arriba). Si alguna vez vuelve una descarga
        # a esta sección, que sea con la decisión tomada a propósito y no por
        # una rama muerta que quedó lista para usarse sin pensarlo.
        assert href == APP, "la sección de descargas ya no enlaza binarios"
        enlace = (f'<a class="btn btn-o" href="{base}app/">{_esc(cta)}'
                  f'{_ico("flecha")}</a>')
        return (f'<article class="d"><b>{_esc(n)}</b><p>{_esc(d)}</p>'
                f'{enlace}<small>{_esc(nota)}</small></article>')

    descargas = "\n".join(_tarjeta_descarga(*item) for item in t["desc_items"])
    items_gratis = "".join(f"<li>{_esc(x)}</li>" for x in t["plan_gratis"])
    items_pago = "".join(f"<li>{_esc(x)}</li>" for x in t["plan_pago"])
    enlaces = "".join(
        f'<a href="#{ancla}">{_esc(txt)}</a>'
        for ancla, txt in zip(("pasos", "video", "idiomas", "descargar", "demo", "precios"),
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
    <a class="btn btn-a" href="{app}"><span class="cta-largo">{_esc(t['hero_cta'])}</span>
      <span class="cta-corto">{_esc(t['nav'][3])}</span></a></div>
</div></nav>

<header class="hero"><div class="wrap">
  <span class="kicker">{_esc(t['hero_k'])}</span>
  <h1>{_esc(t['hero_h1'][0])}<br><span>{_esc(t['hero_h1'][1])}</span></h1>
  <p>{_esc(t['hero_p'])}</p>
  <div class="acciones">
    <a class="btn btn-a" href="{app}">{_esc(t['hero_cta'])}{_ico("flecha")}</a>
    <a class="btn btn-o" href="#pasos">{_esc(t['hero_cta2'])}</a>
  </div>
  <small>{_esc(t['hero_nota'])}</small>
</div></header>

<section id="pasos"><div class="wrap">
  <h2 class="sec-h">{_esc(t['pasos_h'])}</h2>
  <p class="sec-p">{_esc(t['pasos_p'])}</p>
  <div class="pasos">{pasos}</div>
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

<!-- Pedido de demo. Antes acá colgaban los enlaces directos al instalador de
     Windows, al portable, a la edición BAT y al APK: cualquiera se llevaba el
     producto entero sin dejar nombre. Ahora la demo del programa instalado se
     da en vivo — filtra al curioso del prospecto y deja registro de quién
     pidió acceso, con qué correo y desde qué empresa. -->
<section id="demo"><div class="wrap">
  <h2 class="sec-h">{_esc(t['demo_h'])}</h2>
  <p class="sec-p">{_esc(t['demo_p'])}</p>
  <form class="demo-form" id="demo-form" novalidate
        data-error="{_esc(t['demo_error'])}"
        data-ok="{_esc(t['demo_ok'])}"
        data-manual="{_esc(t['demo_manual'])}"
        data-agenda="{_esc(t['demo_agenda'])}"
        data-enviando="{_esc(t['demo_enviando'])}">
    <div><label for="demo-nombre">{_esc(t['demo_nombre'])}</label>
      <input id="demo-nombre" name="nombre" type="text" required minlength="3"
             maxlength="120" autocomplete="name"></div>
    <div><label for="demo-empresa">{_esc(t['demo_empresa'])}</label>
      <input id="demo-empresa" name="empresa" type="text" required minlength="2"
             maxlength="120" autocomplete="organization"></div>
    <div><label for="demo-pais">{_esc(t['demo_pais'])}</label>
      <input id="demo-pais" name="pais" type="text" required minlength="2"
             maxlength="60" autocomplete="country-name"></div>
    <div><label for="demo-email">{_esc(t['demo_email'])}</label>
      <input id="demo-email" name="email" type="email" required maxlength="200"
             autocomplete="email"></div>
    <div class="demo-ancho"><label for="demo-mensaje">{_esc(t['demo_mensaje'])}</label>
      <textarea id="demo-mensaje" name="mensaje" maxlength="1000"></textarea></div>
    <button class="btn btn-a demo-ancho" type="submit">{_esc(t['demo_cta'])}</button>
    <p class="demo-estado demo-ancho" id="demo-estado" role="status" aria-live="polite" hidden></p>
    <p class="demo-nota demo-ancho">{_esc(t['demo_nota'])}</p>
  </form>
</div></section>

<section id="precios"><div class="wrap">
  <h2 class="sec-h">{_esc(t['precios_h'])}</h2>
  <p class="sec-p">{_esc(t['precios_p'])}</p>
  <div class="planes">
    <article class="plan">
      <b>{_esc(t['plan_gratis_t'])}</b>
      <span class="precio">US$ 0</span>
      <span class="precio-nota">&nbsp;</span>
      <ul>{items_gratis}</ul>
      <a class="btn btn-o" href="{app}">{_esc(t['plan_gratis_cta'])}{_ico("flecha")}</a>
    </article>
    <article class="plan destacado">
      <b>{_esc(t['plan_pago_t'])}</b>
      <span class="precio">{_esc(t['plan_pago_precio'])}</span>
      <span class="precio-nota">{_esc(t['plan_pago_nota'])}</span>
      <ul>{items_pago}</ul>
      <button class="btn btn-a" type="button" data-pay="licencia"
              data-error="{_esc(t['plan_pago_error'])}">{_esc(t['plan_pago_cta'])}</button>
    </article>
  </div>

  <!-- La clave que se entrega al volver del pago. Oculta salvo que la URL
       traiga ?pago=ok — ver el script del final. -->
  <div class="pago-vuelta" id="pago-vuelta" hidden
       data-error="{_esc(t['pago_error'])}"
       data-error-h="{_esc(t['plan_pago_error'])}">
    <h3 data-titulo>{_esc(t['pago_ok_h'])}</h3>
    <p>{_esc(t['pago_ok_p'])}</p>
    <code data-clave>…</code>
    <button class="btn btn-a" type="button" data-copiar hidden
            data-listo="{_esc(t['pago_ok_copiado'])}">{_esc(t['pago_ok_copiar'])}</button>
  </div>
</div></section>

<script>
/* Mismo flujo que MV Kobra AI: el botón le pide al backend la preferencia de
   MercadoPago y redirige; la plata cae directo en la cuenta del dueño. */
document.querySelectorAll("[data-pay]").forEach(function (btn) {{
  btn.addEventListener("click", function () {{
    var original = btn.textContent;
    btn.disabled = true; btn.textContent = "…";
    fetch("/api/checkout", {{
      method: "POST",
      headers: {{ "content-type": "application/json" }},
      body: JSON.stringify({{ plan: btn.getAttribute("data-pay") }}),
    }})
      .then(function (r) {{ return r.json().then(function (d) {{ return {{ ok: r.ok, d: d }}; }}); }})
      .then(function (res) {{
        if (res.ok && res.d && res.d.url) {{ window.location.href = res.d.url; return; }}
        btn.disabled = false; btn.textContent = original;
        alert((res.d && res.d.detail) || btn.getAttribute("data-error"));
      }})
      .catch(function () {{
        btn.disabled = false; btn.textContent = original;
        alert(btn.getAttribute("data-error"));
      }});
  }});
}});

/* La vuelta del pago. Antes acá no había NADA: MercadoPago devolvía al
   cliente a /?pago=ok y se terminaba la historia — había pagado y no tenía
   forma de habilitar el programa salvo mandar un correo a mano.

   El `payment_id` que viene en la URL es el comprobante: el backend lo
   verifica contra MercadoPago y devuelve la clave firmada. Nada se guarda,
   así que volver a entrar con el mismo enlace la muestra otra vez. */
(function () {{
  var p = new URLSearchParams(window.location.search);
  if (p.get("pago") !== "ok") return;
  var pid = p.get("payment_id") || p.get("collection_id");
  var caja = document.getElementById("pago-vuelta");
  if (!caja) return;
  caja.hidden = false;
  var salida = caja.querySelector("[data-clave]");
  var titulo = caja.querySelector("[data-titulo]");
  var fallo = function (msg) {{
    titulo.textContent = caja.getAttribute("data-error-h");
    salida.textContent = msg;
    salida.classList.add("pago-falla");
  }};
  if (!pid) {{ fallo(caja.getAttribute("data-error")); return; }}
  fetch("/api/pago/licencia", {{
    method: "POST",
    headers: {{ "content-type": "application/json" }},
    body: JSON.stringify({{ payment_id: pid }}),
  }})
    .then(function (r) {{ return r.json().then(function (d) {{ return {{ ok: r.ok, d: d }}; }}); }})
    .then(function (res) {{
      if (!res.ok || !res.d || !res.d.clave) {{
        fallo((res.d && res.d.detail) || caja.getAttribute("data-error"));
        return;
      }}
      salida.textContent = res.d.clave;
      var b = caja.querySelector("[data-copiar]");
      b.hidden = false;
      b.addEventListener("click", function () {{
        navigator.clipboard.writeText(res.d.clave).then(function () {{
          b.textContent = b.getAttribute("data-listo");
        }});
      }});
    }})
    .catch(function () {{ fallo(caja.getAttribute("data-error")); }});
}})();

/* El pedido de demo. El backend puede responder `enviado:false` sin ser un
   error: significa que no pudo avisar por correo, y entonces devuelve el
   contacto directo. Mostrarlo como falla haría abandonar a alguien que ya
   escribió sus datos, así que se le da la dirección y, si existe, la agenda. */
(function () {{
  var form = document.getElementById("demo-form");
  if (!form) return;
  var estado = document.getElementById("demo-estado");
  var btn = form.querySelector("button[type=submit]");
  var etiqueta = btn.textContent;
  var decir = function (texto, mal, extras) {{
    estado.hidden = false;
    estado.classList.toggle("mal", !!mal);
    estado.textContent = texto;
    (extras || []).forEach(function (nodo) {{
      if (!nodo) return;
      estado.appendChild(document.createTextNode(" "));
      estado.appendChild(nodo);
    }});
  }};
  form.addEventListener("submit", function (ev) {{
    ev.preventDefault();
    if (!form.checkValidity()) {{ form.reportValidity(); return; }}
    var datos = {{}};
    ["nombre", "empresa", "pais", "email", "mensaje"].forEach(function (k) {{
      datos[k] = (form.elements[k].value || "").trim();
    }});
    btn.disabled = true; btn.textContent = form.getAttribute("data-enviando");
    fetch("/api/demo/solicitar", {{
      method: "POST",
      headers: {{ "content-type": "application/json" }},
      body: JSON.stringify(datos),
    }})
      .then(function (r) {{ return r.json().then(function (d) {{ return {{ ok: r.ok, d: d }}; }}); }})
      .then(function (res) {{
        if (!res.ok) {{
          btn.disabled = false; btn.textContent = etiqueta;
          decir((res.d && res.d.detail) || form.getAttribute("data-error"), true);
          return;
        }}
        var agenda = null;
        if (res.d && res.d.agenda) {{
          agenda = document.createElement("a");
          agenda.href = res.d.agenda;
          agenda.target = "_blank";
          agenda.rel = "noreferrer";
          agenda.textContent = form.getAttribute("data-agenda");
        }}
        if (res.d && res.d.enviado) {{
          form.reset();
          btn.textContent = etiqueta;
          decir(form.getAttribute("data-ok"), false, [agenda]);
        }} else {{
          /* El aviso no salió, pero la persona ya escribió sus datos: se le
             da el correo directo Y la agenda. Dejarla con "algo falló" sería
             perder justo al prospecto que se tomó el trabajo de completar. */
          btn.disabled = false; btn.textContent = etiqueta;
          var mail = document.createElement("a");
          mail.href = "mailto:" + ((res.d && res.d.contacto) || "");
          mail.textContent = (res.d && res.d.contacto) || "";
          decir(form.getAttribute("data-manual"), true, [mail, agenda]);
        }}
      }})
      .catch(function () {{
        btn.disabled = false; btn.textContent = etiqueta;
        decir(form.getAttribute("data-error"), true);
      }});
  }});
}})();
</script>

<section class="cierre"><div class="wrap">
  <h2 class="sec-h">{_esc(t['cierre_h'])}</h2>
  <p class="sec-p">{_esc(t['cierre_p'])}</p>
  <a class="btn btn-a" href="{app}">{_esc(t['cierre_cta'])}{_ico("flecha")}</a>
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
