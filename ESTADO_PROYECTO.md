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
| 7 | Descargables PC + Android estilo Kobra (seguridad, SHA-256) | ✅ | Release v1.0.0 al día; landing enlaza `releases/latest` |
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
   `releases/latest/download/…` que usa la landing dejaron de dar 404 a quien
   no tiene sesión de GitHub — era el bloqueo que impedía vender.
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
9. **Estructura de ramas (decisión, no código)** — el repo tiene una sola rama
   y es la que Vercel publica. Para que el merge automático tenga sentido hay
   que volver al flujo `main` + ramas de trabajo con PR, y eso implica
   revisar qué rama tiene Vercel como «Production Branch» antes de cambiar la
   de por defecto. Hasta entonces `automerge.yml` no hace nada (no falla: no
   encuentra PR y sale limpio).

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
