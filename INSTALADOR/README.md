# INSTALADOR · MV Cliente IA para Windows

Hay **dos formas de correr el mismo programa**, para que siempre haya una que
se pueda abrir. Misma interfaz, mismas seis fases, mismos resultados: lo único
que cambia es cómo arranca.

| | **Con instalador (.exe)** | **Sin ningún .exe (BAT)** |
|---|---|---|
| Qué es | Electron + React con el motor FastAPI adentro | El mismo motor, abierto por un `.bat` en tu navegador |
| Necesita | Nada: no pide Python ni dependencias | Python 3.11+ ya instalado en la máquina |
| Cuándo | Es la normal, la que conviene | Cuando la empresa no deja abrir programas descargados |
| Instalación | `MVClienteIA_Setup_demo.exe` | Descomprimir el ZIP y `Instalar.bat` |
| Sin internet | Sí | Sí — trae las dependencias en `vendor\` |

**Las dos** dejan acceso directo en el Escritorio, entrada en el Menú Inicio y
desinstalador en «Agregar o quitar programas». Ninguna pide permisos de
administrador.

## Por qué existe la edición BAT

En muchas empresas AppLocker o SRP bloquean los `.exe` que no vienen de
`Program Files`. El `.bat` esquiva eso porque no aporta ningún ejecutable
propio: usa el `python.exe` que ya está instalado y permitido.

Por eso mismo **no arma un entorno virtual**. Un `venv` copia `python.exe` a
una carpeta del usuario, que es justo lo que esas reglas prohíben ejecutar —
armarlo rompería en la misma máquina para la que existe esta edición. Las
dependencias se instalan con `pip --target` en una carpeta de datos y se corre
el intérprete original.

Tampoco usa Streamlit: sería una segunda interfaz, distinta de la del `.exe` y
del APK, que se desincronizaría a la primera semana. La edición BAT sirve la
**misma** aplicación React.

---

## Las tres ediciones

Es el **mismo programa** las tres veces. Lo único que cambia es un sello que se
hornea al construir; el código es idéntico.

| Edición | Quién la baja | Qué hace |
|---|---|---|
| **demo** | cualquiera, desde la landing | 14 días con todo abierto, sin clave. Vencida, queda el modo demo sintético (la vidriera) y las búsquedas reales piden licencia |
| **cliente** | quien pagó | Pide **una vez** la clave de licencia que llegó con la compra. Con clave válida, sin límite hasta la fecha de vencimiento de la clave |
| **owner** | *sólo vos* — ver `OWNER/` | Sin clave y sin vencimiento. Nunca se publica: este repositorio es público |

### Cómo está ordenada esta carpeta

Sigue el esquema de **MV Agendate IA**: separar lo que baja quien compra de lo
que es sólo tuyo.

```
INSTALADOR/
  Descargar.cmd        ← baja, verifica el SHA-256 y abre (doble click)
  CLIENTE/             ← los hashes de lo que se publica en la Release
  OWNER/               ← tuyo. NO se versiona (ver abajo)
```

### Bajarlas

**Con doble click** (recomendado): abrí `Descargar.cmd` en esta carpeta.
Baja el archivo, **comprueba el SHA-256** contra el que quedó versionado acá
mismo y abre el instalador.

```
Descargar.cmd                → demo, instalador .exe (por defecto)
Descargar.cmd cliente        → la versión comprada, instalador .exe
Descargar.cmd bat            → demo SIN .exe
Descargar.cmd bat-cliente    → la versión comprada, SIN .exe
```

Con un ZIP de la edición BAT lo descomprime solo y te abre la carpeta.

**A mano**, desde la Release:

| Edición | Con instalador | Sin ningún .exe |
|---|---|---|
| demo | `releases/latest/download/MVClienteIA_Setup_demo.exe` | `releases/latest/download/MVClienteIA_BAT_demo.zip` |
| cliente | `releases/latest/download/MVClienteIA_Setup.exe` | `releases/latest/download/MVClienteIA_BAT_cliente.zip` |

Las ediciones con instalador traen además su `_Portable.zip`: se descomprime en
el disco que quieras (`D:\`, un pendrive) y se ejecuta `MVClienteIA.exe` — sin
instalador y sin archivos temporales en `C:`. Es la salida cuando el antivirus
bloquea el NSIS o `C:` está lleno.

### Cómo se usa la edición BAT

1. Descomprimir el ZIP donde quieras.
2. Doble click en **`MVClienteIA.bat`** — se abre en el navegador. La primera
   vez tarda un minuto instalando sus dependencias desde `vendor\`.
3. Opcional: **`Instalar.bat`** deja el acceso directo, el Menú Inicio y el
   desinstalador. **`Desinstalar.bat`** los saca.

Si no hay Python, el propio `.bat` te dice cómo instalarlo. Desde la Microsoft
Store no hace falta ser administrador.

---

## OWNER/ — la edición dueño, y el conversor que la aplica

La edición `owner` abre **sin clave y sin vencimiento**. Lleva el permiso
adentro del archivo, así que en un repositorio público no puede vivir
versionada: cualquiera que clone se llevaría el producto completo.

Por eso `INSTALADOR/OWNER/` **está en `.gitignore`** y se arma en tu máquina:

```bash
python3 packaging/armar_owner.py --codigo TU-CODIGO-LARGO
```

Eso deja dos archivos:

| Archivo | Qué hace |
|---|---|
| `Convertir-a-edicion-dueno.bat` | Pasa una copia **ya instalada** a edición dueño, sin reinstalar 95 MB |
| `LEEME.txt` | El recordatorio de que eso es la llave maestra |

### El conversor busca la instalación solo

Es la diferencia con el de MV Agendate IA, que hay que **copiar a mano**
adentro de la carpeta del programa (si no, avisa que no encontró nada). Acá el
instalador deja **elegir la carpeta** (`allowToChangeInstallationDirectory`),
así que asumir una ruta fija era justamente lo que fallaba. El conversor mira,
en orden:

1. El **registro de Windows** — donde el instalador anota `InstallLocation`.
2. Las carpetas donde Windows instala por defecto (`%LOCALAPPDATA%\Programs`,
   `Archivos de programa`).
3. El **destino real de los accesos directos** del Escritorio y del Menú
   Inicio (resuelve el `.lnk`).
4. Recién por último, la carpeta desde donde se lo ejecutó.

Encuentra las tres formas de entrega: el instalador `.exe` y el portable
dejan el sello en `resources\backend\`; la edición BAT, en `packaging\`.

### Pide tu código de dueño

El conversor convierte **cualquier** copia instalada en la edición completa.
Si se filtra —un chat, una captura, un pendrive— quien lo tenga destraba lo
que vendés. Por eso pide un código: adentro del `.bat` va sólo su **SHA-256**,
nunca el código, así que el archivo suelto no sirve para nada.

Corriéndolo de nuevo ofrece **volver atrás** (guarda un `.original` de cada
sello), así probar la edición dueño no es irreversible.

> Que encuentre la instalación y convierta de verdad lo comprueba el CI en una
> Windows real: instala, corre el conversor **desde otra carpeta**, verifica
> que con el código equivocado no toca nada, que con el correcto el programa
> abre como `owner`, y que la reversión funciona
> (`.github/workflows/build_windows.yml`).

---

## Por qué acá no hay ninguna descarga, sólo hashes

El instalador pesa ~95 MB y el ZIP portable ~126 MB. **GitHub rechaza los
archivos de más de 100 MB**, así que el portable directamente no entra. Y cada
versión que se commitea queda en el historial **para siempre**: con el ritmo de
cambios de este proyecto, el repositorio pasaría de 40 MB a varios GB en un mes,
y cada `git clone` se llevaría todas las versiones viejas.

El ZIP de la edición BAT es mucho más chico (~8 MB, casi todo son las ruedas
de `vendor\`), pero se publica en el mismo lugar por lo mismo: son binarios que
cambian en cada versión.

Todo eso va a la **Release**, que es el lugar de GitHub hecho para eso y no
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
4. Le mandás esa clave y el enlace a **`MVClienteIA_Setup.exe`** —o a
   **`MVClienteIA_BAT_cliente.zip`** si en su empresa no dejan abrir `.exe`.
   La pega una vez en Configuración → Licencia y queda activo. La clave sirve
   igual para las dos formas: es el mismo programa.

La clave está firmada con HMAC-SHA256 sobre un secreto que vive en **tu
máquina** (para emitir) y en **el servidor** (para validar) —
`MVCLIENTE_LICENCIA_SECRETO`. **Nunca dentro de un instalador**, así que nadie
puede sacarlo del `.exe` y emitirse claves.

Por eso activar pide **internet una vez**: el programa manda la clave a
`/api/licencia/validar` y guarda el resultado. Después funciona sin conexión.
El vencimiento se sigue mirando contra el reloj en cada arranque.

**Lo que esto no es:** protección contra alguien que quiera crackear el binario.
Un `.exe` que corre en la máquina del cliente siempre se puede parchear, y el
archivo de activación que queda en disco se puede editar. Vale para este
programa y para cualquier otro que no consulte al servidor en cada uso. Es el
candado honesto que hace que el que paga tenga su clave y el que no, vea el
aviso.

---

## La edición owner está desactivada (y así conviene)

La edición `owner` lleva el permiso **adentro del archivo**: abre sin clave y
sin vencimiento. Lo único que podía protegerla era que el repositorio fuera
privado — y **este repositorio ahora es público**, así que publicarla sería
poner la versión completa a disposición de cualquiera.

**Qué usa el dueño en su lugar:** la edición `cliente` con una clave a su
nombre por muchos años. Es el mismo resultado práctico y además es
**revocable**, cosa que un `.exe` que abre solo no es:

```bash
MVCLIENTE_LICENCIA_SECRETO="tu-secreto" \
  python3 -m cliente_ia.licencia emitir --email vieraschiavi@gmail.com --meses 600
```

Quedan dos redes de seguridad en el workflow por si el repo alguna vez vuelve
a ser privado y se la quiere rehabilitar: la edición está fuera de la lista de
build, y el paso de publicación comprueba la visibilidad del repositorio y
corta si no es `private`.

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
