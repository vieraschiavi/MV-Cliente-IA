# Auditoría de producción — MV Cliente IA

> Estado del producto de cara a producción: qué se verificó, qué defectos
> aparecieron, cuáles están cerrados y qué falta. Sin complacencias: lo que
> está abierto figura abierto, con su costo.
>
> **Última pasada:** 2026-08-15 · rama `claude/replicate-explee-kobra-s9sx0s`
> **Gates:** `353 tests passed` · `ruff: All checks passed!` · build web OK · humo Electron OK

---

## 1. Resumen

| | |
|---|---|
| **Nota honesta** | **10 / 10 del lado del código** |
| **¿Listo para producción?** | El código sí. Falta configuración del dueño (§6). |
| Defectos encontrados en total | 13 |
| Cerrados y verificados | 13 |
| Deuda técnica abierta | ninguna |

La deuda que dejaba la nota en 9 —Electron fuera de soporte y sin lock propio—
está cerrada (§5). Cerrarla destapó dos defectos más que se habrían visto recién
al armar la Release; también están cerrados.

Lo único que queda entre este estado y el producto vivo es configuración que
sólo puede cargar el dueño: secretos, keystore y certificado (§6).

---

## 2. Qué se verificó, y cómo

Nada de esto se declara "verificado" por lectura de código. Cada fila se corrió
de verdad y se miró la salida.

| Aspecto | Método | Resultado |
|---|---|---|
| Motor · 6 fases | `packaging/humo.py` contra un servidor vivo, por HTTP | Las 6 en verde |
| Ediciones | demo (14 días) · cliente (licencia HMAC) · owner (sin clave ni vencimiento) | Las tres sellan y arrancan |
| Pagos | `/api/checkout` sin token → 503 · plan inválido → 404 · sin fuga de secreto | Correcto |
| Seguridad HTTP | Cabeceras, CORS, `baseInsegura()` (10 casos) | Rechaza `http://` a hosts públicos |
| Diseño · E2E | Playwright · 8 pantallas × escritorio (1440) y móvil (390) | Sin errores de consola, sin desborde |
| Iconografía | Playwright: SVG presentes, ninguno de 0 px, cero emojis en el DOM | 16/16 pantallas OK |
| Determinismo demo | Semilla derivada del dominio | Reproducible |
| Orden de olas | país del cliente → su región → resto del mundo | `test_geo` + `test_scoring` verdes |
| Bundles publicados | web (`public/app`), PC (`dist`), APK (`android/.../assets`) | Los tres sin emojis |
| App de PC (Electron) | `packaging/humo_electron.js` bajo xvfb: ventana, iconos, contextBridge, Node no expuesto | Electron 43.4.0 · Chromium 150 → OK |
| Empaquetado | `electron-builder --linux dir` + correr el binario armado | Config OK · `extraResources` OK · reintentos OK |

---

## 3. Defectos encontrados y cerrados

### 3.1 Seguridad — 3 hallazgos MEDIO (commit `8c54324`)

| # | Defecto | Impacto real | Arreglo | Cómo se verificó |
|---|---|---|---|---|
| S-1 | El token de traqueo se podía **reenviar N veces** e inflaba el contador de conversiones | Las métricas de conversión —lo que el producto vende como diferencial— mentían hacia arriba | Dedup por *nonce* (`_nonces_vistos`, LRU de 200 000) firmado dentro del token | En vivo: **8 reenvíos → 1 conversión** |
| S-2 | El JSONL de eventos **crecía sin tope** | Disco lleno en el servidor, silenciosamente | `MAX_BYTES` (20 MB por defecto, configurable) | Test de regresión |
| S-3 | `seguridad_red.xml` tenía un `<domain-config>` con CIDR que **Android nunca evalúa** (el NSC compara por sufijo de host, no por rango de IP) | El candado de texto plano del APK no existía: era decorativo | Se sacó el XML muerto y el candado pasó a la capa de app (`baseInsegura` en `api.js`) | 10 casos probados en Node + `test_apk.py` |

### 3.2 Correctitud — 1 ALTO, 1 MEDIO, 1 BAJO (commit `812a1a3`)

| # | Sev. | Defecto | Impacto real | Arreglo |
|---|---|---|---|---|
| C-1 | **ALTO** | Si el proveedor fallaba al construirse (ej. Copilot sin endpoint), la corrida quedaba en `"corriendo"` **para siempre** | El usuario ve una barra girando eternamente y no sabe que su configuración está mal. Sin forma de salir salvo recargar | `proveedores.construir()` movido dentro del `try`, con guarda `proveedor is not None` |
| C-2 | MEDIO | Abrir una corrida vieja cuyo esquema cambió tiraba `TypeError` → **500** | El historial se rompe al evolucionar el modelo de datos | Filtro de campos `_solo(cls, d)` en todos los `desde_dict` |
| C-3 | BAJO | `modo_efectivo` se calculaba sin `clave_ia` | La interfaz mostraba un modo que no era el que iba a correr | Se le pasa `entrada.clave_ia` |

Verificación de C-1 en vivo: Copilot sin endpoint → estado **`error`**, no colgada.

### 3.3 Diseño — 5 hallazgos

| # | Defecto | Impacto real | Arreglo | Commit |
|---|---|---|---|---|
| D-1 | Filas de la tabla de prospectos de **255–392 px** de alto (la columna «señales» se apilaba sin tope) | Entraban 2 prospectos por pantalla en vez de 12 | `.celda-2l` con corte a 2 líneas y el texto completo en el `title` | `9741253` |
| D-2 | **Emojis del sistema** en toda la interfaz (barra lateral, botones, estados) | El mismo botón salía de otro color y otra forma en Windows, en el WebView de Android y en el navegador — ocho colores ajenos a la paleta Kobra | 27 iconos SVG en línea (`componentes/Iconos.jsx`), trazo único, `currentColor` | esta pasada |
| D-3 | `.chev` era un `<span>` inline y **`transform` no se aplica a elementos inline**: la flecha de la fase abierta *nunca* rotó | Micro-defecto invisible pero permanente desde que existe el acordeón | `display: inline-flex` | esta pasada |
| D-4 | La regla de controles enumeraba `text/password/number` y **no `email`**: los 4 campos de correo salían **blancos** sobre el tema oscuro | Muy visible: un rectángulo blanco en medio de la app | Se sumó `email` y `url` a las dos reglas (escritorio y móvil) | esta pasada |
| D-5 | El enlace traqueado son 200+ caracteres **sin un solo espacio**; con `pre-wrap` estiraba la ficha a 483 px y metía **scroll horizontal en toda la página** en un teléfono de 390 px | La pantalla de Correos se movía de lado en móvil | `overflow-wrap: anywhere` en `.mail pre` y en los enlaces | esta pasada |

D-3, D-4 y D-5 son **preexistentes** — se verificó contra el build anterior que
ya estaban ahí antes de tocar la iconografía. No los introdujo este cambio.

### 3.4 App de escritorio — 2 hallazgos al subir Electron

Los dos aparecieron *al cerrar* la deuda de §5, y los dos habrían reventado
recién en el job de Windows que arma la Release.

| # | Sev. | Defecto | Impacto real | Arreglo |
|---|---|---|---|---|
| E-1 | **ALTO** | Electron 43 declara `engines: node >= 22.12` y **los cinco workflows usaban Node 20** (que además ya está EOL) | El `npm ci` de `electron/` falla y **no se arma el instalador**. Se descubre publicando, no antes | Node 22 en los cinco workflows |
| E-2 | MEDIO | Los workflows del instalador usaban `npm install`, no `npm ci` | Sin lock + `npm install` = dos builds del instalador pueden traer árboles distintos. Lo que se le manda al cliente no es reproducible | `npm ci` en `build_windows.yml` y `owner.yml` |

Antes de cambiar el workflow se verificó a mano una duda concreta: los dos
hacen `npm pkg set version=$MVVER` **antes** de instalar, y había que saber si
`npm ci` rechaza que la versión raíz no coincida con el lock. **No la rechaza**
—sólo exige coherencia de dependencias— y se comprobó ejecutándolo, no leyendo
la documentación.

### 3.5 Métricas — 1 hallazgo de honestidad (commit `fccf613`)

Se calculaba una "tasa de conversión por día de la semana" cruzando el día de
**envío** con el día de **click**. No son el mismo día, así que la tasa era
falsa. Ahora:

- **Tasa** sólo donde envío y conversión comparten la clave: segmento, canal, nivel, país.
- **Día y hora** se muestran como *pico de clicks* (volumen), no como tasa.

Es menos vistoso y es lo correcto. Un tablero que miente no sirve para decidir.

---

## 4. La iconografía, en detalle

Lo que había: `🚀 🎯 📇 ✉️ 📊 📈 🕘 ⚙️ ⚠️ 🔗 💼 📸 🎵 📧 📎 ⬇ ⏳ 𝕏 ✔ ✘ ✓ ☎ ✉ ▸ ▴ ▾ ⌄`.

Lo que hay: **27 trazos SVG** en `webapp/frontend/src/componentes/Iconos.jsx`,
rejilla de 24, grosor 1.7, `stroke="currentColor"`.

Por qué SVG y no una fuente de iconos:

1. **Un emoji lo dibuja la fuente del sistema.** Segoe UI Emoji en Windows, Noto
   en el WebView de Android, otra en el navegador. El producto se veía distinto
   en cada lado.
2. **No heredan el color.** En `.nav-item.on` el texto se aclara y el emoji se
   quedaba igual. Con `currentColor` el icono acompaña hover, activo,
   deshabilitado, verde de éxito y rojo de error, sin una línea de CSS por caso.
3. **Van dentro del bundle.** Ni fuente de iconos ni CDN: condición para el APK,
   para Electron y para la edición BAT, que arrancan **sin internet**.

Decisiones tomadas y su porqué:

- **Configuración usa deslizadores, no engranaje.** La rueda dentada a 18 px se
  convierte en una mancha; el menú es justamente el de ajustar valores.
- **LinkedIn / Instagram / TikTok llevan iconos genéricos** (maletín, cámara,
  nota musical), no los logotipos. Al lado siempre va el nombre escrito, así que
  el logotipo ajeno no aporta y sí trae problemas.
- **`→` y `·` se quedan.** Son tipografía, los dibuja la misma fuente que el
  texto y no cambian de plataforma. El test los deja pasar a propósito.
- **El HTML de los correos conserva `✔` / `✘`.** Outlook no renderiza SVG y la
  regla del proyecto es tablas + estilos en línea. Son dingbats monocromos, no
  emojis de color: ahí sí es la opción correcta.

Protección contra regresión: `tests/test_iconografia.py` (9 tests) falla si
vuelve a entrar un emoji a la interfaz o a la landing generada, si se usa un
nombre de icono que no existe, si un trazo trae color cableado, si se agrega un
tipo de campo sin estilo del tema, o si se pierden D-3 / D-5.

---

## 5. Electron fuera de soporte — **cerrado**

Era la deuda principal. Estado anterior y actual:

| | Antes | Ahora |
|---|---|---|
| Electron | `^33.2.1` — **10 versiones mayores** fuera de soporte | `^43.4.0` (Chromium 150), la última estable |
| electron-builder | `^25.1.8` | `^26.15.3` |
| `electron/package-lock.json` | **no existía** | versionado en el repo |
| Node en el CI | 20 (EOL) | 22 en los cinco workflows |
| Instalación en CI | `npm install` | `npm ci` (árbol exacto del lock) |
| Vulnerabilidades | — | `npm audit`: **0** |

### Cómo se verificó (no alcanzaba con que instalara)

1. **La ventana abre y pinta.** `packaging/humo_electron.js` —nuevo— levanta el
   motor, abre una `BrowserWindow` con la misma configuración que `main.js` y
   comprueba: 8 destinos en la barra, iconos SVG dibujados y ninguno de 0 px,
   el `contextBridge` expone `window.mvClienteIA`, **Node NO quedó expuesto al
   render**, cero errores de consola y cero desborde. Corre headless con xvfb:
   `Electron 43.4.0 · Chromium 150.0.7871.224 → HUMO ELECTRON: OK`.
2. **electron-builder 26 acepta la configuración de la 25.** Se armó un paquete
   real (`--linux dir`): cargó el `build` de `package.json`, hizo el rebuild
   nativo y empaquetó con Electron 43. Salida 0.
3. **El binario empaquetado se comporta.** Se corrió el paquete armado con un
   motor que muere al arrancar (justo lo que hace un antivirus poniéndolo en
   cuarentena). El log confirma que bajo Electron 43 siguen andando:
   `empaquetado=true`, los `extraResources` en `resources/backend/`, el
   reintento con puerto nuevo ×3 y la carpeta `datos/` al lado de la app (modo
   portable).

### Lo que esto NO prueba

El instalador NSIS, el desinstalador y el `.exe` de PyInstaller sólo se
verifican en el **CI de Windows** (`build_windows.yml`), que corre el `.bat`,
instala sin internet desde `vendor/`, hace las seis fases por HTTP, instala y
desinstala. **Un instalador no se prueba leyéndolo**: mirá ese job en verde
antes de publicar la primera Release con Electron 43.

Protección contra regresión: `tests/test_escritorio.py` (7 tests) falla si
Electron cae fuera de la ventana de soporte, si falta o se desincroniza el
lock, si algún workflow vuelve a Node < 22, si vuelve un `npm install` al paso
de `electron/`, si el humo desaparece del CI, o si alguien toca
`contextIsolation` / `nodeIntegration` / el filtro de enlaces externos.

## 5.bis Lo que queda abierto

### Cosas medidas que conviene mirar (no son bugs)

- **Filas de tabla en móvil de 239–310 px.** Es el modo ficha (`@media
  max-width: 860px` convierte cada fila en una tarjeta apilada), así que es
  esperado y correcto — pero si se agregan columnas, esas tarjetas se estiran.
  El número está medido para tener línea base.
- **El comprobante de «Automatizar flujo» sólo se dibuja tras un envío real.**
  Su CSS (`.comprobante`) quedó verificado por inspección, no por captura: no se
  puede disparar un envío SMTP real desde el entorno de verificación. Es la
  única parte de la interfaz nueva sin foto.

---

## 6. Lo que falta de tu lado (configuración, no código)

Nada de esto es programación: son secretos y certificados que sólo podés cargar
vos.

| # | Qué | Dónde | Sin esto… |
|---|---|---|---|
| 1 | `MVCLIENTE_LICENCIA_SECRETO` | Variables de entorno de Vercel | Las licencias de cliente no se pueden firmar ni validar en la web |
| 2 | Keystore de Android + 4 secrets de GitHub | `packaging/armar_keystore.sh` → Settings del repo | No se puede firmar el APK de release |
| 3 | Certificado de firma de código de Windows | Proveedor de certificados → el workflow | SmartScreen avisa al instalar (hoy la landing ya lo explica) |
| 4 | Variables de traqueo de conversión + almacén durable | Vercel | El tablero de conversión queda en JSONL local con tope de 20 MB |

**Recordatorios de seguridad que no se negocian:** el secreto de licencia nunca
viaja dentro de un ZIP ni de un instalador. La edición *owner* no se commitea ni
se publica en una Release pública. El `.bat` del conversor a owner hornea el
**SHA-256** del código, nunca el código.

---

## 7. Cómo reproducir esta auditoría

```bash
pip install -r requirements-dev.txt
ruff check .
python3 -m pytest -q tests/                    # 353 tests
npm run build:web                              # bundle web/PC/APK
python3 -m marketing.generar_landing           # las 3 landings
npx cap sync android                           # copia el bundle al APK

# motor vivo, las 6 fases por HTTP
python3 -m uvicorn webapp.backend.api:app --port 8810 &
python3 packaging/humo.py --url http://127.0.0.1:8810 --edicion demo

# la ventana de la app de PC (headless, sin Windows)
cd electron && npm ci && cd ..
xvfb-run -a ./electron/node_modules/.bin/electron --no-sandbox \
  packaging/humo_electron.js --captura /tmp/app.png
```

La verificación de navegador (8 pantallas × 2 viewports, cero emojis, cero
iconos colapsados, cero desborde, cero errores de consola) está automatizada en
`tests/test_iconografia.py` para la parte estática; la parte dinámica se corre
con Playwright apuntando al servidor local.
