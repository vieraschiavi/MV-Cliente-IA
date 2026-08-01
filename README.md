# MV Cliente IA

**Pegá el enlace de tu producto y el agente te trae los clientes.** Investiga tu
empresa, explora la competencia, define campañas, encuentra empresas objetivo,
ubica a los decisores y escribe los correos — priorizando **Uruguay primero,
después LATAM, después el resto del mundo**, y en **tres idiomas** (español,
portugués e inglés).

Es una réplica del flujo *auto-GTM* de [explee.com](https://explee.com) construida
sobre el stack y el diseño de **MV Kobra AI**: mismo tema navy + verde, misma
arquitectura (React + Vite al frente, FastAPI atrás, Electron para PC), y ahora
también **APK de Android**.

---

## Las seis fases

| # | Fase | Qué hace |
|---|------|----------|
| 1 | **Investigá tu empresa** | Lee tu sitio y extrae qué vendés, a quién, con qué argumento y en qué mercado. |
| 2 | **Explorá la competencia** | Contra quién te compara tu comprador, y cuánto se solapan. |
| 3 | **Definí campañas** | Un ángulo de mensaje por sector × ola geográfica. |
| 4 | **Encontrá clientes potenciales** | Empresas que encajan en el perfil, con la señal de *por qué ahora*. |
| 5 | **Encontrá a los decisores** | Quién firma la decisión en cada empresa, con cargo y seniority. |
| 6 | **Escribí los correos** | Un primer contacto y su seguimiento, **en el idioma del país de quien lo recibe**. |

---

## La regla que define el producto: Uruguay primero

No es un filtro que se enciende y se apaga — **el orden vive adentro del puntaje**
(`cliente_ia/geo.py` + `cliente_ia/scoring.py`):

```
score = 100 × ajuste_icp × peso_geográfico

peso_geográfico:   Uruguay 1.00   ·   LATAM 0.72   ·   Resto del mundo 0.45
```

Y además la lista se **ordena por ola antes que por puntaje**, así que ni siquiera
un prospecto perfecto de Estados Unidos puede colarse delante de uno uruguayo
flojo. Eso está cubierto por un test dedicado
(`tests/test_scoring.py::test_orden_respeta_la_ola_aunque_el_de_afuera_sea_mejor`),
porque es la regla que más fácil se rompe sin querer al recalibrar pesos.

El reparto de la tanda es 45 % Uruguay / 35 % LATAM / 20 % resto. Las tres olas
arrancan a la vez a propósito: si fuera estrictamente secuencial, LATAM y el
mundo no recibirían un solo correo hasta agotar Uruguay, y el producto nunca
probaría los otros dos idiomas en la calle.

## Los tres idiomas

- **La interfaz** la elegís vos (ES / PT / EN), y queda guardada en el equipo.
- **El correo, no**: sale en el idioma del **país del decisor**. A Brasil se le
  escribe en portugués aunque vos trabajes en español; a Alemania, en inglés.

Cada texto del correo —propuesta de valor, dolor del sector, diferencial— viaja
en los tres idiomas desde la fase 1, para que no quede un párrafo en español en
medio de un correo en inglés. Hay un test que lo verifica marca por marca
(`test_los_correos_no_mezclan_idiomas`).

---

## Origen de los datos: tres modos

| Modo | Qué usa | Cuándo |
|------|---------|--------|
| `demo` | Catálogo sintético determinista, sin red | Demo comercial y tests. **Por defecto.** |
| `web` | Lee el HTML público de tu sitio (fase 1) + demo para el resto | Cuando querés que la investigación sea real. |
| `llm` | + API de Claude para competencia, campañas y empresas objetivo | Con `ANTHROPIC_API_KEY`. |

### Honestidad sobre los datos

Es la misma convención que MV Kobra AI: **los datos sintéticos se dicen sintéticos.**

- En modo `demo`, las **empresas** y las **personas** son generadas por
  combinatoria: viajan con `sintetico: true`, la interfaz muestra un cartel y el
  CSV lleva una columna `sintetico`. No representan organizaciones ni individuos
  reales; cualquier parecido es casualidad.
- Los **sectores**, **cargos** y **ciudades** del catálogo sí son taxonomía
  pública real.
- El modo `llm` propone **organizaciones** (información pública de mercado) pero
  **nunca personas**: la fase 5 queda siempre en manos del proveedor sintético.
  Armar listas de individuos reales con sus datos de contacto es justamente lo
  que este producto no hace.
- Si usás el modo de investigación real, **revisá la información antes de
  contactar a nadie**, y respetá las reglas de correo comercial del país de
  destino (en Uruguay, la Ley 18.331 de protección de datos personales).

---

## Arrancar

```bash
pip install -r requirements.txt

# 1) Motor por línea de comandos (no necesita nada más)
python3 -m cliente_ia.pipeline mvkobranzaia.com --modo demo --prospectos 60 --nombre "MV Kobra AI"

# 2) Frontend + backend
cd webapp/frontend && npm install && npm run build && cd ../..
python3 -m uvicorn webapp.backend.api:app --port 8810
#   → http://localhost:8810
```

En desarrollo, con recarga en caliente del frontend:

```bash
cd webapp/frontend && npm run dev     # Vite en :5173, proxya /api a :8810
```

### Comandos

| Acción | Comando |
|--------|---------|
| Corrida end-to-end | `python3 -m cliente_ia.pipeline <dominio>` |
| Tests | `python3 -m pytest -q tests/` |
| Linter | `ruff check .` |
| Backend | `python3 -m uvicorn webapp.backend.api:app --port 8810` |
| Landing (3 idiomas) | `python3 -m marketing.generar_landing` |
| Build web | `npm run build:web` |
| APK de Android | `npm run apk:debug` |
| App de PC | `cd electron && npm install && npm start` |

---

## Los tres empaquetados

### Navegador
El backend sirve el build de React desde el mismo origen. Nada que instalar.

### PC (Windows) — Electron
`electron/main.js` levanta el motor en un puerto libre de `127.0.0.1` y abre la
ventana ahí. El motor se empaqueta con PyInstaller (`packaging/mvclienteia.spec`)
y electron-builder lo mete en el instalador:

```bash
pip install pyinstaller
cd webapp/frontend && npm run build && cd ../..
pyinstaller packaging/mvclienteia.spec --noconfirm
cd electron && npm install && npm run dist        # → electron/dist_installer/
```

### Android — Capacitor
El APK empaqueta la **misma** interfaz React (mismo CSS, mismo i18n: por debajo
de 860 px la barra lateral pasa a ser una barra inferior y las tablas se leen
como fichas).

```bash
export ANDROID_HOME=$HOME/android-sdk
npm install
npm run apk:debug     # → android/app/build/outputs/apk/debug/app-debug.apk
```

> **El APK no lleva el motor adentro.** Python no corre dentro de un APK, así
> que la app apunta a un backend por HTTP: la primera vez hay que poner la
> dirección del servidor en **Configuración** (por ejemplo
> `http://192.168.1.10:8810`, o tu dominio si lo desplegás). El botón «Probar
> conexión» confirma antes de guardar. Si tu servidor está en internet, ponele
> contraseña (ver abajo) y serví por HTTPS.

---

## Seguridad

- **`MVCLIENTE_PASSWORD`**: si está definida, la API exige
  `Authorization: Bearer <token>` y el token se saca de `POST /api/auth/login`.
  Si no está, la API queda abierta — es el modo del instalador de PC, donde el
  servidor escucha sólo en `127.0.0.1`. **Para cualquier despliegue expuesto a
  internet la variable es obligatoria.**
- Los ids de corrida se validan contra `[A-Za-z0-9_-]{1,64}`: no se "limpian",
  se rechazan.
- El servido estático verifica que el archivo pedido esté contenido dentro del
  build, sin confiar en que el framework normalice la ruta.

## Dónde se guardan los datos

Una corrida = un JSON. En el repo, bajo `datos/corridas/`; instalado, en la
carpeta del usuario (`%LOCALAPPDATA%\\MVClienteIA` en Windows). La escritura es
atómica, porque el backend guarda el avance después de *cada* fase.
`MVCLIENTE_DIR_DATOS` fuerza el directorio (lo usan los tests).

---

## Estructura

```
cliente_ia/            motor
  geo.py               Uruguay → LATAM → mundo · idioma por país
  scoring.py           la fórmula del puntaje, explicable línea por línea
  modelos.py           Empresa · Competidor · Campana · Prospecto · Decisor · Email
  pipeline.py          orquesta las 6 fases y publica el avance
  redaccion.py         fase 6 — plantillas de correo en es/pt/en
  proveedores/         demo (sintético) · web (tu sitio real) · llm (Claude)
  datos/mercado.json   semilla del catálogo de mercado
webapp/backend/api.py  FastAPI + servido del build
webapp/frontend/       React + Vite (tema de MV Kobra AI, i18n es/pt/en)
electron/              app de PC
android/               proyecto Capacitor
landing/               landing en es · pt · en (generada)
packaging/             PyInstaller
tests/                 61 tests
```

## Estado verificado

- `python3 -m pytest -q tests/` → **61 pasan**; `ruff check .` limpio.
- Corrida end-to-end sobre `mvkobranzaia.com` en modo `demo` y en modo `web`
  (leyendo el sitio real: detecta el nombre, el mercado UY y los tres idiomas
  que Kobra publica).
- Interfaz probada con Playwright en escritorio (1440×960) y en móvil (Pixel 7):
  las seis fases completan, las tres olas aparecen y los correos salen en ES, PT
  y EN, sin errores de consola.
- El payload que va **dentro del APK** probado por separado: arranca sin backend,
  se configura la dirección del servidor, corre el pipeline completo y muestra
  los correos en los tres idiomas.
