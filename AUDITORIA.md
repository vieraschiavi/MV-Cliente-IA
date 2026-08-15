# Auditoría de producción — MV Cliente IA

> Estado del producto de cara a producción: qué se verificó, qué defectos
> aparecieron, cuáles están cerrados y qué falta. Sin complacencias: lo que
> está abierto figura abierto, con su costo.
>
> **Última pasada:** 2026-08-15 · rama `claude/replicate-explee-kobra-s9sx0s`
> **Gates:** `346 tests passed` · `ruff: All checks passed!` · build web OK

---

## 1. Resumen

| | |
|---|---|
| **Nota honesta** | **9 / 10** |
| **¿Listo para producción?** | El código sí. Falta configuración del dueño (§6). |
| Defectos encontrados en total | 11 |
| Cerrados y verificados | 11 |
| Deuda técnica abierta | 1 (Electron sin soporte, §5) |

El punto que falta para el 10 no es un bug: es la dependencia de Electron fuera
de su ventana de soporte y sin `package-lock.json` propio. Está explicado en §5.

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

### 3.4 Métricas — 1 hallazgo de honestidad (commit `fccf613`)

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

## 5. Lo que falta mejorar (abierto)

### 5.1 Electron fuera de soporte — **la deuda principal**

- `electron/package.json` pide `electron: ^33.2.1`. Electron mantiene sólo las
  últimas versiones mayores: la 33 ya no recibe parches de seguridad, y arrastra
  su propia versión de Chromium.
- **No hay `electron/package-lock.json`.** La raíz y `webapp/frontend/` sí lo
  tienen y están versionados; el subproyecto de Electron no. Sin lock, dos
  builds del instalador en fechas distintas pueden traer árboles de
  dependencias distintos.

**Riesgo real:** un CVE de Chromium sin parche en el instalador de PC, y builds
no reproducibles. No rompe hoy; es lo que más acerca el producto al 10.

**Trabajo estimado:** subir a una versión mayor con soporte, congelar el lock,
y volver a correr el CI de Windows de punta a punta (que ya existe: corre el
`.bat`, instala sin internet desde `vendor/`, hace las 6 fases por HTTP,
instala y desinstala). Es acotado, pero **hay que verificarlo en una Windows de
verdad** antes de publicar: un instalador no se prueba leyéndolo.

### 5.2 Cosas medidas que conviene mirar (no son bugs)

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
python3 -m pytest -q tests/                    # 346 tests
npm run build:web                              # bundle web/PC/APK
python3 -m marketing.generar_landing           # las 3 landings
npx cap sync android                           # copia el bundle al APK

# motor vivo, las 6 fases por HTTP
python3 -m uvicorn webapp.backend.api:app --port 8810 &
python3 packaging/humo.py --url http://127.0.0.1:8810 --edicion demo
```

La verificación de navegador (8 pantallas × 2 viewports, cero emojis, cero
iconos colapsados, cero desborde, cero errores de consola) está automatizada en
`tests/test_iconografia.py` para la parte estática; la parte dinámica se corre
con Playwright apuntando al servidor local.
