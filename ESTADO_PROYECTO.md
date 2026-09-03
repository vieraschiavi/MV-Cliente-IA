# MV Cliente IA · Acta de estado del proyecto

> Última verificación completa: 2026-08-03 · commit `ac6868b` · 107 tests ·
> batería de producción 16/16. Este documento es la constancia de qué se pidió,
> qué se entregó y qué depende del dueño para operar al 100%.

## Qué es y dónde vive

Réplica del flujo auto-GTM de explee.com sobre el stack y diseño de MV Kobra
AI: se pega la URL de un producto y el agente investiga la empresa, mapea la
competencia directa, arma campañas, encuentra compradores, ubica decisores y
escribe los correos — Uruguay → LATAM → mundo, en es/pt/en.

| Canal | Dónde |
|-------|-------|
| Web | https://mv-cliente-ia.vercel.app (landing + app, es/pt/en) |
| PC Windows | Release v1.0.0: `MVClienteIA_Setup.exe` (instalador con panel de marca, icono en Escritorio, Menú Inicio, desinstalador) y `MVClienteIA_Portable.zip` (100 % en el disco elegido) |
| Android | Release v1.0.0: `MVClienteIA.apk` (WebView contra el servidor configurado en Ajustes) |
| Código | github.com/vieraschiavi/MV-Cliente-IA · rama `claude/replicate-explee-kobra-s9sx0s` |

## Todo lo pedido, con su estado

| # | Pedido | Estado | Evidencia |
|---|--------|--------|-----------|
| 1 | Pipeline de 6 fases estilo explee (investigar → correos) | ✅ | 107 tests; corrida real en producción |
| 2 | El país del cliente primero (elegible, ~100 países), luego su región, luego mundo | ✅ | tests de olas relativas (`test_geo`); corrida en producción con Japón → 11 JP / 8 Asia / 5 mundo |
| 3 | Tres idiomas (es/pt/en); el idioma del receptor manda | ✅ | tests de no-mezcla de idiomas |
| 4 | Video demo propio, voz humana rioplatense (es-UY), pt/en nativas, sin lag, mostrando TODOS los dashboards (incl. competencia y análisis) | ✅ | videos 71/79/72 s servidos en producción |
| 5 | Campo de clave de IA en la app | ✅ | Configuración → Investigación con IA |
| 6 | Multi-proveedor: Claude / ChatGPT / Gemini / Copilot (Azure) | ✅ | verificado vivo con claves falsas (401/400 firmados por proveedor); Claude por REST en la app de PC |
| 7 | Descargables PC + Android estilo Kobra (seguridad, SHA-256) | ✅ | Release v1.0.0 al día con su SHA-256. Desde 2026-08-21 la landing YA NO los enlaza: son el canal de entrega de quien compra (ver «La demo del programa instalado NO es pública») |
| 8 | Instalador con elección de disco/carpeta, iconos, desinstalador, panel de marca; edición portable 100 % en el disco elegido | ✅ | build 23 success; NSIS es/pt/en |
| 9 | Puertos sin choques (PC) | ✅ | puerto libre + reintentos en Electron/lanzador |
| 10 | Búsqueda con IA relevante al rubro real (no catálogo) | ✅ | perfil, competencia, campañas y prospectos desde el texto real del sitio |
| 11 | Filtro de mercado (todos/UY/LATAM/mundo) aplicado de verdad, también en competencia | ✅ | recorte en código + país visible en cada competidor + nota honesta si no hay locales |
| 12 | Nicho real según web y producto (no "Software B2B" genérico) | ✅ | paso `perfilar` con IA; aviso cuando se corre sin clave |
| 13 | URL de panel/JS no produce perfil de otro producto | ✅ | detección por palabra + resumen vacío + aviso "pegá la URL pública" |
| 14 | Contactos: no inventar personas; conseguir mails y datos reales | ✅ | rastreador de contactos PÚBLICOS del sitio de cada empresa (correo comercial, teléfono, LinkedIn, Instagram); decisor = cargo + gente actual de la empresa en LinkedIn filtrada por cargo |
| 15 | Envío automático de correos + adjuntos; LinkedIn/X directo | ✅ | SMTP del usuario (credenciales que se usan y descartan), lote sin casillas sintéticas, adjunto ≤5 MB; composer LinkedIn/X (no hay API abierta de mensajes) |
| 16 | Pestaña Análisis: prob. de éxito, mercado potencial, FODA de competidores, rentabilidad con/sin ads, 3 escenarios a 3-24 meses, sin inventar | ✅ | matemática pura con supuestos declarados + cualitativo sólo con clave; desglose ventas/gastos/neto; móvil con títulos |
| 17 | Web: cada uno con su clave; 3 búsquedas gratis avisadas, por correo válido; dueño sin límite; precios + MercadoPago como Kobra | ✅ | cupo cookie+IP+correo; `vieraschiavi@gmail.com` exento; licencia US$ 149 / ≈$U 6.000; checkout integrado (falta el token, ver abajo) |
| 18 | Resultados en streaming (no esperar todo junto) | ✅ | NDJSON por fase, verificado vivo |
| 19 | Datos sintéticos siempre marcados; jamás personas reales con contacto | ✅ | regla de diseño, cubierta por tests |
| 20 | Reels verticales 9:16 para redes (estilo Instagram: rótulos, resaltes, contador, CTA), en 3 idiomas, voz Kobra sin lags | ✅ | `python3 -m marketing.generar_reel` → `/reel/{es,pt,en}/reel.mp4`; silencios entre escenas recortados de ~1,9 s a ~0,6 s (también en el demo 16:9) |
| 21 | Prospectos en tramos 50/100/200/500/1000 (sin tope en 60) | ✅ | selector con los 5 tramos; API `le=1000`; test de la corrida de 1000 completa |
| 22 | «Automatizar flujo»: 1 click envía todo y llega comprobante | ✅ | correos por SMTP + post real en X + mensajes de LinkedIn por el proveedor del usuario + cola manual honesta (IG/TikTok) + comprobante HTML a la casilla; tests del lote, del 502 y del tachado de secretos |
| 23 | LinkedIn automatizado de verdad (como los bots que le llegan al dueño) | ✅ | `cliente_ia/redes.py`: LinkedIn NO tiene API pública de mensajes, así que se integra el proveedor de sesión que el usuario contrata (Unipile), resolviendo el perfil `/in/…` a su identificador. El riesgo de restricción de cuenta se avisa ANTES de pegar la clave |
| 25 | Recuadro con presentador en los reels (como los reels de referencia) | ✅ | `marketing/presentador/{es,pt,en}.mp4`: el clip se compone sobre todas las escenas y avanza entre cortes; la tarjeta de la captura se achica sola para dejarle lugar. Sin clip, el reel sale como antes |
| 26 | Carpeta `INSTALADOR/` + tres ediciones (demo / cliente / owner) | ✅ | `cliente_ia/licencia.py` con clave firmada HMAC-SHA256; demo de 14 días que se vence sola; owner sin clave, en Release aparte marcada prerelease; 15 tests, incluido «una clave firmada con otro secreto no pasa» |
| 24 | Dashboard de métricas por red y por publicación | ✅ | pestaña Métricas: correos enviados/intentados, mensajes de LinkedIn, posts de X con impresiones/likes/respuestas/reposts en vivo desde la API de X; historial en el dispositivo (el web es serverless y no tiene disco) |

## Automatización del repositorio

| Qué | Cuándo se dispara | Qué hace |
|-----|-------------------|----------|
| `ci.yml` | todo push a **cualquier** rama y todo PR | ruff + pytest + corrida end-to-end + build del frontend |
| `build_windows.yml` | push que toca `packaging/`, `electron/`, `cliente_ia/`, `webapp/` — **y sólo si ruff y los tests pasan** | `MVClienteIA_Setup.exe` + portable ZIP a la Release |
| `apk.yml` | push que toca `webapp/frontend/`, `android/`, capacitor — **y sólo si el frontend compila** | `MVClienteIA.apk` a la Release |
| `automerge.yml` | cuando el CI termina en verde sobre un PR | mergea con squash y **borra la rama**, si el PR lleva la etiqueta `automerge` y no es borrador |

**Bug encontrado y arreglado (2026-08-07):** `ci.yml` decía `branches: [main]`.
Cuando `main` se borró y la rama de trabajo pasó a ser la de por defecto, el CI
dejó de correr **sin avisar**: quince commits seguidos sin linter ni tests del
lado del servidor. Ahora no tiene filtro de rama — un filtro que nombra una
rama que puede desaparecer es un interruptor de apagado silencioso.

**El repositorio pasó a ser PÚBLICO (2026-08-08).** Tres consecuencias:

1. **Las descargas de los clientes ya funcionan.** Los enlaces
   `releases/latest/download/…` dejaron de dar 404 a quien no tiene sesión de
   GitHub — era el bloqueo que impedía vender. (Desde el 2026-08-21 la landing
   ya no los publica: se le pasan a quien compra. La Release sigue siendo el
   canal, no la vidriera.)
2. **GitHub Actions es gratis e ilimitado** en repos públicos con runners
   estándar. La cuota que tenía frenados todos los workflows deja de aplicar.
3. **La edición `owner` se desactivó.** Lleva el permiso adentro del `.exe` y
   lo único que la protegía era que el repo fuera privado. El dueño usa la
   edición `cliente` con una clave a su nombre por 600 meses: mismo resultado
   y, a diferencia de un binario que abre solo, revocable.

Revisión de seguridad al abrir el repo: sin secretos en el árbol ni en el
historial (se buscaron los patrones de MercadoPago, Anthropic, OpenAI, Google
y GitHub), sin archivos `.env` ni claves versionadas, y `datos/` —donde viven
las corridas con contactos— está en `.gitignore`, así que nunca se publicó.

**⚠️ La cuenta de GitHub estuvo en el tope de su cuota (2026-08-07).** Al
arreglar el disparador, el CI corrió por primera vez en cinco días y dio dos
datos:

1. La corrida `fe2b5fa` ejecutó de verdad: **el motor pasó entero** (ruff,
   pytest y la corrida end-to-end) y el frontend compiló en 1,86 s. El job
   quedó rojo sólo por `upload-artifact` → *«Artifact storage quota has been
   hit»*. Ese paso se sacó: no le servía a nadie.
2. La corrida siguiente (`34eb3b5`) murió **en 4 segundos**, con los dos jobs
   sin logs. Los jobs llegaron a crearse, así que no es un error de sintaxis:
   es la cuenta contra su límite de gasto de Actions.

O sea: **los workflows están bien y el código está verde**; lo que falta es
levantar el límite en GitHub (Settings → Billing → Spending limit) o esperar a
que la cuota se recalcule, cosa que GitHub hace cada 6-12 horas. Hasta que eso
pase, ningún workflow del repo va a poder correr — ni el CI, ni el instalador
de Windows, ni el APK, ni el auto-merge.

**Sobre el merge automático:** hoy el repositorio tiene **una sola rama**
(`claude/replicate-explee-kobra-s9sx0s`), que además es la de por defecto y la
que Vercel publica en producción. No hay merge que automatizar porque no hay
rama destino. `automerge.yml` queda listo y probado para cuando se trabaje con
ramas + PR; recrear `main` como rama por defecto es una decisión del dueño
porque **cambia de dónde despliega Vercel** (ver abajo).

## ⚠️ Lo que depende del dueño (no es código)

1. **`MERCADOPAGO_ACCESS_TOKEN` en Vercel** — ✅ configurado por el dueño
   (2026-08-03). El token de la cuenta EGGON fue validado antes (producción,
   crea checkouts OK). Recomendado: renovar el token en el panel de
   MercadoPago (quedó pegado en un chat) y actualizar el valor en Vercel.
2. **`MVCLIENTE_OWNER` en Vercel** — ✅ configurado por el dueño (2026-08-03).
   El mismo código se pega en la app (Configuración → Código de dueño) para
   quedar exento del cupo con candado fuerte.
3. **Clave de IA propia** para búsquedas reales y análisis cualitativo
   (Claude / ChatGPT / Gemini / Copilot) — se pega en Configuración; el
   servidor la usa y la descarta. Opcional: `ANTHROPIC_API_KEY` en Vercel si
   se quiere ofrecer IA sin clave del visitante (corre por cuenta del dueño).
4. **SMTP del remitente** para el envío real de correos (en la app:
   Configuración → Envío de correos; Gmail requiere contraseña de aplicación).
5. **Prueba de humo en Windows físico** — el Setup compila y publica bien
   desde CI, pero el doble-click final en una máquina real lo confirma el
   dueño (2 min): instalar, abrir, correr una demo, desinstalar.
6. **Dominio propio (opcional)** — hoy el sitio vive en `*.vercel.app`.
   `mvclienteia.com` (el que dicen los videos) está **libre**: US$ 11,25/año
   desde Vercel, o se compra en cualquier registrador y se apunta al proyecto.
7. **Cuota de GitHub Actions** — la cuenta está en su tope: los workflows
   fallan en segundos y sin logs, y los artifacts no se pueden subir. Se
   resuelve en Settings → Billing → Spending limit, o esperando el recálculo
   (6-12 h). No es un problema del código: la última corrida real dejó el
   motor en verde.
8. **`MVCLIENTE_LICENCIA_SECRETO` en Vercel** — el secreto con el que se
   firman y validan las claves. Va como variable de entorno **del servidor**
   (nunca en un instalador: el programa activa en línea contra
   `/api/licencia/validar`). Guardalo: si lo perdés, las claves ya emitidas
   dejan de validar. Generar uno:
   `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.
   Emitir la clave de un comprador:
   `MVCLIENTE_LICENCIA_SECRETO=... python3 -m cliente_ia.licencia emitir --email X --meses 12`.
   Mientras no lo definas, cae a `MVCLIENTE_OWNER`, que ya está configurado —
   así que el sistema funciona hoy, pero conviene separarlos.
   **Actualización:** `POST /api/pago/licencia` existía en el backend desde
   antes, pero nada en el frontend lo llamaba — el comprador pagaba, volvía a
   `/?pago=ok` y ahí terminaba todo. Se agregó `PagoConfirmado.jsx`: lee esa
   query al volver de MercadoPago, canjea el `payment_id` por la clave, la
   deja activada sola en ese dispositivo y la muestra en pantalla para que el
   comprador la guarde también en la PC o el Android. Cubierto por Playwright
   contra un backend con MercadoPago simulado (aprobado / pendiente / vuelta
   rota sin `payment_id`).
9. **Estructura de ramas (decisión, no código)** — el repo tiene una sola rama
   y es la que Vercel publica. Para que el merge automático tenga sentido hay
   que volver al flujo `main` + ramas de trabajo con PR, y eso implica
   revisar qué rama tiene Vercel como «Production Branch» antes de cambiar la
   de por defecto. Hasta entonces `automerge.yml` no hace nada (no falla: no
   encuentra PR y sale limpio).

10. **`MVCLIENTE_SMTP_HOST` / `_PUERTO` / `_USUARIO` / `_CLAVE` / `_SSL` en
    Vercel** — con esto el formulario de demo (ver abajo) te avisa por correo
    apenas alguien pide acceso, con `Reply-To` puesto en quien lo pidió: le
    contestás apretando «responder». **Sin esto el formulario igual funciona**:
    responde `enviado:false`, le muestra a la persona tu correo directo y deja
    el pedido en el log del servidor — nunca se traga un prospecto en silencio.
    Pero el aviso automático no sale, así que hay que mirar los logs.
11. **`MVCLIENTE_URL_AGENDA` en Vercel (opcional)** — el enlace de tu agenda
    (Calendly, Google Calendar). Si está, después de mandar el formulario
    aparece el botón «Agendar ahora» y la persona reserva sola. Vacío = no se
    ofrece ninguna agenda, que es lo correcto: no prometer un recurso que no
    existe.

## La demo del programa instalado NO es pública (2026-08-21)

Hasta este cambio la landing colgaba los cuatro binarios con enlace directo
—instalador de Windows, portable, edición BAT y APK, todos en su variante
demo de 14 días—. Cualquiera que abriera la página se llevaba **el artefacto
de ingeniería entero** y no quedaba registro de quién.

Ahora:

- **La landing no enlaza ni un binario.** Lo cubre
  `tests/test_instalacion.py::test_la_landing_no_ofrece_descargar_ningun_binario`,
  que mira el HTML generado (no el generador: el bug volvería agregando un
  ítem a `desc_items` y el `.py` se seguiría leyendo igual de bien).
- **Lo que se muestra solo es el resultado, no el producto:** el visitante
  abre la app en el navegador, con datos sintéticos y sin instalar nada.
- **La demo completa se pide** en la sección `#demo` (nombre completo,
  empresa, país y correo obligatorios) y se muestra en una reunión 1:1 — que
  además es una oportunidad de vender mientras mostrás, no de que miren solos
  y se vayan.
- **Los binarios se siguen publicando en la Release** (`build_windows.yml` y
  `apk.yml`, cada uno con su SHA-256): son el canal de entrega de quien compra
  la licencia. Lo que cambió es a quién se le ofrecen.

12. **`MVCLIENTE_TRAQUEO_SECRETO` y `MVCLIENTE_URL_TRAQUEO`** — las DOS
    encienden la medición de interacción (tasa de apertura, clicks y tráfico).
    Sin ellas el correo sale **sin pixel** y los enlaces salen directos: es
    una función que se prende a propósito, no un rastreador por default. El
    panel avisa cuando están apagadas, para que un 0% no se lea como un
    fracaso comercial cuando en realidad no se está midiendo.
    Generar el secreto: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.
    `MVCLIENTE_URL_TRAQUEO` es la URL pública del backend (la de Vercel).

    **Dónde persiste, según dónde corra.** El programa instalado (PC/BAT)
    tiene disco y acumula solo. La web pública (serverless) NO: el disco se
    borra entre invocaciones. Para eso está `cliente_ia/almacen_kv.py`, que
    guarda en **Vercel KV** (Upstash Redis) por REST — sin dependencias
    nuevas, con `urllib`. Se enciende solo cuando existen las variables:

    - En Vercel: **Storage → Create Database → KV**, y conectarlo al
      proyecto. Vercel inyecta `KV_REST_API_URL` y `KV_REST_API_TOKEN` sin
      que haya que copiar nada. (Un store de Upstash creado a mano también
      sirve: se leen `UPSTASH_REDIS_REST_URL` / `_TOKEN`.)
    - Sin esas variables el código sigue usando el archivo, y el panel del
      dueño lo avisa con todas las letras: un número bajo puede ser «no se
      está midiendo», no «el producto no funciona».

    El store arregla además algo que el archivo no podía: el dedup de nonces
    vivía en memoria del proceso, y en serverless eso no deduplicaba nada —
    reproducir el enlace de un correo inflaba la conversión en la web
    pública aunque el test con disco pasara perfecto. Con KV es un `SET NX`
    atómico compartido entre instancias.

13. **Lectura de la casilla (IMAP), para contar respuestas** — se carga en el
    programa (Configuración → «Leer la casilla»), no en el servidor: las
    credenciales viven en el navegador del usuario y viajan sólo con cada
    consulta. Es un permiso APARTE del SMTP a propósito —mandar y leer son
    dos cosas distintas— y el producto funciona igual sin él: sólo que no
    cuenta respuestas. Con Gmail hace falta una contraseña de aplicación.

    Qué hace exactamente: abre la casilla en **modo lectura** (no puede
    marcar, mover ni borrar nada), pide sólo las cabeceras `In-Reply-To`,
    `References` y `Date` con `BODY.PEEK` (que además no marca como leído) y
    cruza contra los Message-ID que emitimos. **El cuerpo de un correo no se
    abre nunca.** Está cubierto por un test que falla si alguien pide más que
    cabeceras.

14. **Aviso por correo cuando alguien aprieta «Comprar»** — no cuando paga:
    en el CLICK, antes de que exista ningún pago. Reusa el SMTP de
    `MVCLIENTE_SMTP_*` (el mismo del formulario de demo). Sirve para prender
    Vercel Pro en el proyecto justo antes de que llegue tráfico real, en vez
    de pagarlo especulativamente en los 10 proyectos. Silencio de 30 minutos
    (`MVCLIENTE_AVISO_COMPRA_SILENCIO_S`) para que clickear varias veces no
    llene la casilla; si el SMTP falla o no está configurado, el checkout
    sigue funcionando igual — perder el aviso es aceptable, perder la venta
    no. El correo aclara explícitamente que es el click y no la venta
    confirmada, para no prender/apagar infraestructura por una visita que se
    arrepintió.

## Auditoría entrega-verificada (2026-08-27)

Pedido: confirmar que se corrigieron los errores históricos del proyecto y
certificar la plataforma de pago de punta a punta. Se ejecutó el protocolo
del skill nuevo `.claude/skills/entrega-verificada/`.

**Primer intento (descartado, no se ocultó):** un workflow de 6 agentes en
paralelo + verificación adversarial falló en seco — los 6 agentes de
revisión no pudieron usar ninguna herramienta (`StructuredOutput retry cap
exceeded`) y el único que devolvió texto lo dijo explícito: *"el permission
handler está rechazando todas las llamadas, incluso `ls`"*. El resultado
crudo era `"confirmados": []`, que NO se reportó como "todo limpio" — un
diagnóstico aparte confirmó que un sub-agente normal SÍ tenía herramientas
funcionando en ese momento, así que el fallo fue puntual de ese mecanismo,
no de la sesión entera.

**Segundo intento (el que valió):** las mismas 6 dimensiones, corridas a
mano con el Agent tool (pagos, hardening, correctitud de backend,
frontend/i18n/imágenes, video/audio por idioma, regresión de las 12 reglas
de CLAUDE.md), cada hallazgo verificado por mí releyendo el código citado
antes de tocar nada.

| Dimensión | Resultado |
|---|---|
| Pagos y licencia | 1 hallazgo real corregido (renovación gratis re-canjeando el mismo pago). 1 hallazgo (código de dueño horneado en el APK owner) ya estaba mitigado y cubierto por `test_el_bundle_publicado_no_lleva_codigo_de_dueno_horneado` — descartado. |
| Hardening de infraestructura | 1 hallazgo real corregido (secreto de cupo gratis cae a una constante pública si no hay ni `MVCLIENTE_OWNER` ni `MVCLIENTE_PASSWORD`). 1 hallazgo (spoofing de `X-Forwarded-For`) descartado como falso positivo: la documentación de Vercel confirma que sobreescriben ese header y no reenvían IPs externas salvo un proxy de confianza (Enterprise). |
| Correctitud de backend | 1 hallazgo real corregido, el más importante de los cuatro: el secreto de sesión (login) era aleatorio por proceso — en Vercel, un cold start invalidaba tokens vigentes emitidos por la instancia anterior. |
| Frontend, i18n e imágenes | i18n: 0 diferencias entre es/pt-BR/en (comparación automatizada). Imágenes: `public/banners/captura_es.png` y `captura_en.png` tenían la última columna de la tabla cortada por el borde — **no era un bug de código**, `landing/banners/` ya estaba bien desde un fix anterior, sólo faltaba correr `marketing.armar_sitio` para republicarlo. Corregido. |
| Video y audio por idioma | Sin hallazgos. Guion traducido de verdad (no el mismo texto subtitulado), voces nativas por idioma (`es-UY-MateoNeural` / `pt-BR-AntonioNeural` / `en-US-GuyNeural`), audios con hash distinto entre los tres. Límite declarado: un agente de texto no transcribe el habla, así que no se verificó la pronunciación en sí. |
| Regresión de reglas de negocio | 475 tests corridos, todos verdes. 11 de las 12 reglas de CLAUDE.md tenían test dedicado; la regla 2 (nombre del producto por idioma) sólo tenía tests que comprobaban que las claves de i18n no estuvieran vacías, nunca que el VALOR coincidiera entre las 4 fuentes (i18n × 3, `generar_landing.py`, Android). Se agregó el test que faltaba. |

**Se corrigieron 4 hallazgos reales** (commits `a2c20cd` y `f2ed7b2`), con
tests de regresión nuevos para los tres de código (478 tests verdes en
total, +3 sobre los 475 previos) y republicación de assets para el de
imágenes. **Se descartaron 2 hallazgos** con evidencia (test existente /
documentación oficial de la plataforma), no por conveniencia.

**Huecos de cobertura que esta auditoría NO cerró** (quedan para una
próxima vuelta, no se inventó que se hicieron):

- No se probó un pago real (ni en sandbox de MercadoPago) de punta a punta
  contra el backend corriendo — se leyó y se testeó el código, no se vio un
  pago volver de verdad.
- No se corrió un escaneo de dependencias con CVEs conocidos
  (`pip-audit`/`npm audit`) sobre `requirements*.txt` ni sobre `vendor/` de
  la edición BAT.
- No hay rate-limiting en `/api/pago/licencia` más allá de que MercadoPago
  sólo devuelve pagos de la cuenta propia del dueño.
- El bypass del cupo gratis por correo sintético (sin verificación real de
  que el solicitante lo controla) queda como limitación conocida y
  documentada en el propio código — no se implementó verificación por
  correo (OTP/magic-link) porque es una función nueva, no un bug.
- No se instaló el APK en un dispositivo/emulador real ni se corrió el
  `.bat` en Windows físico como parte de esta pasada (eso lo cubre el CI de
  Windows dedicado, ver más arriba).

## Puesta en producción: configuración, licencias y edición owner (2026-08-27)

Tres cosas que faltaban para que el circuito «el cliente paga → recibe su
licencia → la usa» cierre solo, más la entrega de la versión completa al dueño.

### 1. `.env.example` — toda la configuración en un solo lugar

Archivo versionado con **todas** las variables que el proyecto lee, de dónde
sale el valor de cada una y qué pasa exactamente si falta. No lleva ningún
valor: sólo nombres. `tests/test_configuracion.py` lo mantiene sincronizado en
los dos sentidos —falla si el código lee una variable que el archivo no
documenta, y también si el archivo documenta una que ya nadie lee— y verifica
que ninguna línea tenga un valor cargado, porque el repositorio es público y
una clave commiteada queda en el historial para siempre.

### 2. Webhook de MercadoPago: la venta que se perdía entera

Hasta acá la licencia se emitía **sólo** si el comprador volvía a
`/?pago=ok&payment_id=…`. Eso cubre la tarjeta aprobada al instante y nada
más. Los dos casos que se caían son justamente los del mercado del producto:

- **Pagos en efectivo que se aprueban horas después** — Abitab y Redpagos en
  Uruguay, Rapipago y Pago Fácil en Argentina, y las transferencias en
  cualquier lado. Para cuando MercadoPago aprueba, el comprador cerró el
  navegador hace rato: nunca hubo vuelta al sitio, nunca se emitió la clave.
  Pagó y no recibió nada.
- El que cierra la pestaña antes de que termine la redirección.

`POST /api/webhook/mercadopago` cierra eso: MercadoPago avisa al aprobar, se
verifica la firma `x-signature` (HMAC-SHA256 sobre la plantilla
`id:…;request-id:…;ts:…;`), se emite la licencia y **se le manda por correo al
comprador** sin que nadie haga nada. `/api/pago/licencia` queda como está: es
el camino inmediato y el que le permite recuperar la clave si la pierde.

Sin `MERCADOPAGO_WEBHOOK_SECRET` el endpoint **rechaza todo con 401**, a
propósito: emite licencias, así que sin firma no hay forma de distinguir un
aviso real de uno inventado por cualquiera que conozca la URL. Cubierto por
tres tests, incluido el de que una firma de otro pago no se puede reusar.

**Falta hacerlo del lado de MercadoPago:** Tus integraciones → Webhooks,
evento `payment`, URL `https://mv-cliente-ia.vercel.app/api/webhook/mercadopago`,
y copiar la «clave secreta» a `MERCADOPAGO_WEBHOOK_SECRET` en Vercel.

### 3. `LICENSE` y `EULA.txt`

El proyecto vendía software propietario sin ninguno de los dos. Se agregaron,
siguiendo el mismo criterio que el repositorio de MV Tasación IA (mismo autor,
misma jurisdicción). El EULA lleva además tres cláusulas propias de ESTE
producto, que no son decorativas:

- **Datos de contacto y correo en frío** — quien usa el programa es el
  responsable del tratamiento de esos datos y de cumplir la Ley 18.331, el
  GDPR, la LGPD o CAN-SPAM según corresponda. Los correos salen de SU casilla,
  con SUS credenciales.
- **Automatización de LinkedIn** — va contra su Acuerdo de Usuario y puede
  terminar en la cuenta restringida. Corre por cuenta y riesgo del usuario.
- **Resultados como estimaciones** — puntajes, análisis y proyecciones son
  apoyo, no asesoramiento ni garantía de ventas.

Conviene que un abogado los revise antes de la primera venta grande; están
escritos siguiendo los del producto hermano, no son un dictamen legal.

### 4. La edición owner ahora SE PUBLICA (decisión del dueño)

Estaba desactivada porque el repositorio es público y la edición owner lleva
el permiso adentro del archivo. El dueño pidió tenerla disponible igual para
poder probar la versión completa de un click, se le señaló la consecuencia y
la asumió explícitamente.

`.github/workflows/owner.yml` ahora publica la Release **`owner-latest`**
(etiqueta fija, marcada *prerelease*) con el instalador y el portable, y
versiona sus `.sha256` en `INSTALADOR/OWNER/`, que además trae un
`Descargar-OWNER.cmd` de doble click que baja, verifica el hash y abre.

**Cualquiera que encuentre esa Release se lleva el producto completo sin
pagar.** Para cerrarlo: borrar la Release `owner-latest`, volver a
`contents: read` en ese workflow y sacar el paso de publicación.
`build_windows.yml` conserva intacta su propia red de seguridad (ahí la
edición owner sigue fuera del build y el paso de publicación corta si el repo
no es privado).

## Competencia sembrable, pasada local con «todos» y envío a un botón (2026-09-03)

Pedido del dueño con caso concreto: Mozart —competidor uruguayo real de MV
Kobra AI— no aparecía en la fase 2 con ningún prompt, y quería mandar correos
y LinkedIn a los decisores con UN botón. Tres cambios:

1. **«Competidores que ya conocés»** (Explorar → Enlaces del mensaje).
   Ningún modelo conoce a todas las empresas chicas de un mercado chico; el
   que mejor conoce a su competencia es el dueño del producto. Los dominios
   que nombre entran PRIMEROS a la fase 2, con el país deducido del TLD
   (`geo.pais_de_dominio`), marcados como vendedores del mercado (pasan el
   recorte) y, si hay huella verificable, con el rubro MEDIDO sobre su propia
   web — pero nunca descartados por medir bajo: la afirmación del dueño pesa
   más que una portada hecha de imágenes. Un nombre sin dominio («Mozart» a
   secas) no se convierte en un dominio inventado: se avisa qué falta
   (regla 5). Verificado con Playwright contra la app real: el sembrado
   aparece primero, con UY y sin carteles de fallo.

2. **La pasada local de competencia corre también con mercado «todos»** (el
   default). Antes sólo corría con «sólo mi país»/«mi región»: con el filtro
   por defecto, diez competidores extranjeros y ni un local, sin que nadie
   fuera a buscarlo — contradiciendo «tu país primero». Con «mundo» sigue sin
   correr: ahí el usuario excluyó su país a propósito.

3. **«Enviar todo: correo + LinkedIn» en un solo botón** (Correos). Un solo
   pedido a `/api/automatizar` con los dos canales —el backend siempre los
   aceptó juntos; la separación era de la interfaz—, un solo comprobante, y
   las métricas registradas POR CANAL para que el panel siga sumando correos
   con correos. Sólo se ofrece cuando los dos canales están configurados
   (SMTP + proveedor de LinkedIn); si falta uno, quedan los botones por canal
   que dicen qué falta.

Suite completa en verde (499: 469 + 30 de navegador), ruff limpio, frontend
compilado y E2E del sembrado corrido contra el backend vivo.

## Cómo re-verificar todo (5 min)

```bash
pip install -r requirements-dev.txt
ruff check . && python3 -m pytest -q tests/     # motor + API
npm run build:web                                # frontend
python3 -m uvicorn webapp.backend.api:app --port 8810   # y probar en el navegador
```
En producción: `GET /api/salud` → ok; una corrida en modo «Leer mi sitio» con
un correo válido; la pestaña Análisis con números de ejemplo; las descargas
desde la portada.
