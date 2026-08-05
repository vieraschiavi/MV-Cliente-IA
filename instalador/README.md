# MV Cliente IA · Instalador de Windows

Punto único de descarga e instalación del **programa de PC**. Es un programa
nativo: al abrirlo levanta su propio motor en tu computadora y muestra el
tablero en su ventana — **no abre el navegador ni depende de la web**, y tus
datos no salen de la máquina.

## Descargar

| Archivo | Cuándo usarlo | Enlace |
|---------|---------------|--------|
| `MVClienteIA_Setup.exe` | Instalación normal. Asistente en es/pt/en, elegís carpeta y disco, deja icono en el Escritorio y en el Menú Inicio, y desinstalador en «Agregar o quitar programas». No pide permisos de administrador. | [Descargar](https://github.com/vieraschiavi/MV-Cliente-IA/releases/latest/download/MVClienteIA_Setup.exe) |
| `MVClienteIA_Portable.zip` | Sin instalar, 100 % en el disco que elijas (`D:\`, un pendrive). Descomprimís y ejecutás `MVClienteIA.exe`. No escribe nada en la carpeta temporal de `C:`. | [Descargar](https://github.com/vieraschiavi/MV-Cliente-IA/releases/latest/download/MVClienteIA_Portable.zip) |
| `MVClienteIA.apk` | Android. Es un cliente: apunta al servidor que configures en Ajustes. | [Descargar](https://github.com/vieraschiavi/MV-Cliente-IA/releases/latest/download/MVClienteIA.apk) |

Los binarios viven en la **Release** del repositorio, no en el árbol de
archivos: un `.exe` de 95 MB y un ZIP de 126 MB dentro de Git quedarían en el
historial para siempre (y el ZIP supera el límite de 100 MB por archivo de
GitHub). La Release es el lugar que GitHub tiene justamente para esto, y es a
donde apuntan los botones de la portada.

> **Importante — visibilidad del repositorio.** Estos enlaces sólo funcionan
> para quien tenga acceso al repositorio. Si el repositorio está **privado**,
> un comprador recibe `404` al tocar Descargar. Ver
> [«Distribución a compradores»](#distribución-a-compradores).

## Verificar la descarga

Cada archivo se publica con su `.sha256` al lado. En PowerShell:

```powershell
Get-FileHash .\MVClienteIA_Setup.exe -Algorithm SHA256
```

El resultado tiene que coincidir con el contenido del `.sha256`. Si no
coincide, la descarga se cortó o fue alterada: bajala de nuevo.

## Instalar

1. Doble clic en `MVClienteIA_Setup.exe`.
2. Windows puede mostrar **SmartScreen** («Windows protegió tu PC»): el
   instalador no está firmado con certificado de código. → *Más información*
   → *Ejecutar de todas formas*.
3. Elegís idioma, carpeta y disco. Al terminar queda el icono en el
   Escritorio y en el Menú Inicio.
4. Al abrir, aparece la pantalla «Iniciando el motor en tu equipo…» y en unos
   segundos el tablero.

## Si no arranca

La causa número uno es el **antivirus o Windows Defender** poniendo en
cuarentena `MVClienteIA.exe` (el motor), porque va sin firma de código.

1. Seguridad de Windows → *Protección contra virus y amenazas* →
   *Administrar la configuración* → *Exclusiones* → agregar la carpeta de
   instalación.
2. Volver a abrir el programa.
3. Si el antivirus sigue molestando, usar la **edición Portable**.

El programa deja un registro de arranque que dice exactamente qué falló:
**Ayuda → Ver registro de arranque** (o `datos\mvclienteia.log` al lado del
ejecutable; si esa carpeta no es escribible, `%TEMP%\MVClienteIA\`).

## Una sola versión para todos

No existe una compilación distinta para el dueño y otra para los compradores:
**CI construye un único `MVClienteIA_Setup.exe` por versión** y ese mismo
archivo es el que publica la Release y el que enlaza la portada. El `.sha256`
publicado permite comprobarlo: si el hash de tu archivo es igual al de la
Release, es literalmente el mismo binario.

El «código de dueño» (`MVCLIENTE_OWNER`) **no cambia el programa**: sólo exime
del cupo de 3 búsquedas gratis del **sitio web**. En el programa de PC no hay
cupo — el motor es tuyo y corre en tu máquina, sin límite de búsquedas.

## Puertos

El programa **no puede chocar con otro puerto abierto**: al arrancar le pide
al sistema operativo un puerto libre y usa ése, y si en el instante entre
pedirlo y tomarlo otra aplicación se lo gana, detecta la falla al instante y
reintenta con un puerto nuevo (hasta 3 veces). Verificado con el puerto por
defecto ocupado a propósito: el motor elige otro y avisa cuál.

## Distribución a compradores

Para que los botones de descarga de la portada funcionen para cualquiera hay
tres caminos; el 1 es el recomendado para un producto que se vende:

1. **Repositorio de descargas público, código privado.** Se crea un
   repositorio aparte (por ejemplo `MV-Cliente-IA-descargas`), público y
   vacío salvo sus Releases, y se suben ahí los tres archivos. El código
   fuente sigue privado. Hay que actualizar los enlaces de la portada
   (`marketing/generar_landing.py` → `URL_EXE`, `URL_ZIP`, `URL_APK`).
2. **Este repositorio público.** Los enlaces funcionan al instante, pero
   queda expuesto todo el código del producto que estás vendiendo.
3. **Almacenamiento externo** (Vercel Blob, Cloudflare R2, S3). Enlaces
   propios y control de acceso, con un paso de subida por versión.
