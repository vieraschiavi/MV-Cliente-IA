# INSTALADOR · MV Cliente IA para Windows

El programa de escritorio: **Electron + React con el motor FastAPI adentro**.
No usa Streamlit, no pide Python ni instalar dependencias — se baja, se
instala y se abre como cualquier programa de Windows.

El instalador deja **acceso directo en el Escritorio**, **entrada en el Menú
Inicio** y **desinstalador en «Agregar o quitar programas»**. No pide permisos
de administrador y deja elegir la carpeta (sirve para instalar en `D:\` o donde
haya lugar).

---

## Las tres ediciones

Es el **mismo programa** las tres veces. Lo único que cambia es un sello que se
hornea al construir; el código es idéntico.

| Edición | Quién la baja | Qué hace |
|---|---|---|
| **demo** | cualquiera, desde la landing | 14 días con todo abierto, sin clave. Vencida, queda el modo demo sintético (la vidriera) y las búsquedas reales piden licencia |
| **cliente** | quien pagó | Pide **una vez** la clave de licencia que llegó con la compra. Con clave válida, sin límite hasta la fecha de vencimiento de la clave |
| **owner** | **sólo el dueño**, desde este repositorio | Sin clave y sin vencimiento. No se publica en la Release pública |

### Bajarlas

**Con doble click** (recomendado): abrí `Descargar.cmd` en esta carpeta.
Baja el archivo, **comprueba el SHA-256** contra el que quedó versionado acá
mismo y abre el instalador.

```
Descargar.cmd            → demo (por defecto)
Descargar.cmd cliente    → la versión comprada
Descargar.cmd owner      → la del dueño (necesita GitHub CLI autenticado)
```

**A mano**, desde la Release:

| Edición | Enlace |
|---|---|
| demo | `releases/latest/download/MVClienteIA_Setup_demo.exe` |
| cliente | `releases/latest/download/MVClienteIA_Setup.exe` |
| owner | Release aparte `owner-vX.Y.Z`, marcada como prerelease |

Cada una trae además su `_Portable.zip`: se descomprime en el disco que quieras
(`D:\`, un pendrive) y se ejecuta `MVClienteIA.exe` — sin instalador y sin
archivos temporales en `C:`. Es la salida cuando el antivirus bloquea el NSIS o
`C:` está lleno.

---

## Por qué acá no hay ningún `.exe`

El instalador pesa ~95 MB y el ZIP portable ~126 MB. **GitHub rechaza los
archivos de más de 100 MB**, así que el portable directamente no entra. Y cada
versión que se commitea queda en el historial **para siempre**: con el ritmo de
cambios de este proyecto, el repositorio pasaría de 40 MB a varios GB en un mes,
y cada `git clone` se llevaría todas las versiones viejas.

Los binarios van a la **Release**, que es el lugar de GitHub hecho para eso y no
tiene ese costo. Acá queda lo que sí conviene versionar:

- `Descargar.cmd` — el doble click que baja, verifica y abre.
- `*.sha256` — 89 bytes cada uno, y permiten comprobar que el archivo que bajó
  un comprador es **exactamente** el que compiló el CI.

Si preferís los binarios adentro del repo igual, se puede con Git LFS. Decilo y
lo cambio, pero con LFS la cuota de ancho de banda se paga aparte.

---

## Cómo se le vende a un cliente

1. El cliente baja **`MVClienteIA_Setup_demo.exe`** desde la landing y tiene
   14 días completos, sin poner nada.
2. Cuando se le vence (o antes), paga desde la sección Precios.
3. Vos le emitís la clave:
   ```bash
   MVCLIENTE_LICENCIA_SECRETO="tu-secreto" \
     python3 -m cliente_ia.licencia emitir --email cliente@empresa.com --meses 12
   ```
4. Le mandás esa clave y el enlace a **`MVClienteIA_Setup.exe`**. La pega una
   vez en Configuración → Licencia y queda activo.

La clave está firmada con HMAC-SHA256 sobre un secreto que **sólo tenés vos**
(`MVCLIENTE_LICENCIA_SECRETO`). El programa la **verifica**, pero no puede
fabricarla: el secreto no viaja en ningún instalador.

**Lo que esto no es:** protección contra alguien que quiera crackear el binario.
Un `.exe` que corre en la máquina del cliente siempre se puede parchear — vale
para este programa y para cualquier otro. Es el candado honesto que hace que el
que paga tenga su clave y el que no, vea el aviso.

---

## ⚠️ La edición owner

Lleva el permiso **adentro del archivo**. Lo único que la protege es que **este
repositorio es privado**. Dos consecuencias:

- Si ese `.exe` se filtra, quien lo tenga tiene la edición completa para
  siempre.
- **Si alguna vez hacés público el repositorio, borrá primero la Release
  `owner-v*`.** Está marcada como prerelease para que no la agarre ningún
  enlace `latest`, pero pública sería visible igual.

Si preferís no tener ese riesgo, la alternativa es no compilar la edición owner
y usar la `cliente` con una clave que emitas a tu nombre por 50 años: mismo
resultado práctico, y sin un binario que abra solo.

---

## Verificar la descarga a mano

```powershell
Get-FileHash MVClienteIA_Setup.exe -Algorithm SHA256
```
Tiene que coincidir con el contenido de `MVClienteIA_Setup.exe.sha256`.

## Si Windows muestra «Windows protegió tu PC»

Es SmartScreen: el instalador todavía no tiene firma de código (un certificado
EV cuesta unos US$ 300/año). **Más información → Ejecutar de todas formas**.
El SHA-256 de esta carpeta es la forma de comprobar que el archivo es el que
compiló el CI y nadie lo tocó en el camino.

## Puertos

El programa levanta su backend en `127.0.0.1` en un **puerto libre que busca al
arrancar** — no choca con nada que ya tengas abierto. Sólo escucha en local:
nada queda expuesto a la red.
