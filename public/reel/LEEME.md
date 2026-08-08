# Reels verticales para redes

Los videos cortos VERTICALES (9:16, 720×1280) para publicar en Instagram,
TikTok o YouTube Shorts, uno por idioma:

```
landing/reel/es/reel.mp4
landing/reel/pt/reel.mp4
landing/reel/en/reel.mp4
```

Son una pieza distinta del demo de la landing (`landing/video/`, 16:9): el
lenguaje acá es el de un reel — fondo estrellado, rótulos estilo terminal,
titulares con la palabra clave en verde, la app en modo móvil dentro de una
tarjeta, chips de canales, un contador que sube y subtítulos con las palabras
importantes en amarillo. Cierra con el llamado a la acción: la web y las tres
búsquedas gratis.

El sitio los publica en `/reel/<idioma>/reel.mp4` para poder enlazarlos o
bajarlos desde cualquier lado, pero la landing no los muestra: son material
para redes, no para la página.

**Con tu cara en un recuadro**: dejá un clip tuyo en `marketing/presentador/`
(ver el LEEME de esa carpeta) y todos los reels lo llevan abajo, como los reels
que funcionan en Instagram. Sin clip salen igual que ahora — no se inventa una
cara.

Los produce `python3 -m marketing.generar_reel`: levanta el backend, corre la
corrida demo, captura la app en su layout de teléfono (el mismo del APK) y
pone la locución neural de cada idioma. Igual que la landing, los banners y el
demo: si hay que cambiar una escena o un texto, se cambia el generador y se
regenera — nunca se edita un video a mano. Un reel grabado con una persona
real puede reemplazar a cualquiera de los tres cuando exista: mismo nombre de
archivo y listo.
