# OWNER · la versión completa, para probarla vos

Acá está el instalador de la **edición dueño**: el programa entero, sin clave
de licencia y sin vencimiento. Es idéntico en funciones a lo que recibe un
cliente que paga la versión full — la única diferencia es que no pide clave.

## Bajarla (doble click, no precisa nada más)

Abrí **`Descargar-OWNER.cmd`**. Baja el instalador, le comprueba el SHA-256
contra el hash versionado en esta misma carpeta y te lo abre.

O a mano, desde el navegador:

| Qué | Enlace |
|---|---|
| Instalador | `releases/download/owner-latest/MVClienteIA_Setup_owner.exe` |
| Portable (sin instalar, en el disco que quieras) | `releases/download/owner-latest/MVClienteIA_Portable_owner.zip` |

Se actualizan **solas** en cada build: `.github/workflows/owner.yml` compila,
prueba que abra sin clave y republica la Release `owner-latest`. Siempre hay
una reciente sin que tengas que acordarte de lanzar nada.

## Ojo: esto es público

Este repositorio es **público**, así que esa Release la puede bajar cualquiera
que la encuentre. Fue una decisión tomada a conciencia para poder probar la
versión completa cómodo, pero conviene tenerlo presente:

- Quien la baje tiene el producto entero sin pagar.
- Está marcada como *prerelease* para que no aparezca como «latest» ni la
  agarre ningún enlace de la landing, pero eso **no la esconde**.
- El día que quieras cerrarla: borrá la Release `owner-latest` y volvé a poner
  `contents: read` en `owner.yml`. La alternativa sin exposición es pasar el
  repositorio a privado (así está el de MV Tasación IA) o usar la edición
  `cliente` con una clave a tu nombre por muchos años, que además es
  revocable:

  ```bash
  MVCLIENTE_LICENCIA_SECRETO="tu-secreto" \
    python3 -m cliente_ia.licencia emitir --email vieraschiavi@gmail.com --meses 600
  ```

## Por qué en una Release y no como archivo del repositorio

Es el mismo criterio que ya usa `INSTALADOR/CLIENTE/`, y no es una preferencia
de estilo: son tres límites concretos.

1. **El portable no entra.** Pesa ~126 MB y GitHub **rechaza** los archivos de
   más de 100 MB. Commitearlo es imposible, no incómodo.
2. **El instalador tampoco tiene margen.** Pesa ~95 MB: 5 MB abajo del corte.
   Un `push` que lo pase de 100 MB falla y rompe el workflow entero.
3. **Cada versión quedaría para siempre.** Git guarda todas: con 95 MB por
   build, el repositorio pasa de 40 MB a varios GB en un mes, y cada `git
   clone` se baja todas las versiones viejas.

Una Release no tiene ninguno de los tres problemas (2 GB por archivo,
almacenamiento aparte del historial) y da una URL directa estable. Acá quedan
los `.sha256`, que ocupan 89 bytes y sirven para verificar que el archivo que
bajaste es exactamente el que compiló el CI.

## El conversor, para no rebajar 95 MB

Si ya tenés el programa instalado (cualquier edición), no hace falta bajar el
instalador owner de nuevo: `packaging/armar_owner.py` arma un
`Convertir-a-edicion-dueno.bat` que busca la instalación sola y le escribe el
sello de la edición dueño.

```bash
python3 packaging/armar_owner.py --codigo TU-CODIGO-LARGO
```

Ese `.bat` **no se versiona** (está en `.gitignore`): convierte cualquier copia
instalada en la edición completa, así que es la llave maestra del producto. Por
eso además pide tu código de dueño — adentro del archivo va sólo su SHA-256,
nunca el código, así que si se filtra no sirve para nada.

Corriéndolo de nuevo ofrece volver atrás: guarda un `.original` de cada sello.
