# Videos de la landing y de los correos

Poné acá el video de demostración, uno por idioma:

```
landing/video/es/demo.mp4
landing/video/pt/demo.mp4
landing/video/en/demo.mp4
```

Los tres los usa la sección `#video` de la landing y —salvo que se configure
otra URL— son a los que apuntan el correo y el mensaje de LinkedIn, cada
receptor al de **su** idioma.

Si preferís tenerlos en YouTube, Vimeo o un CDN, no hace falta copiarlos acá:
pasá la URL de cada idioma al lanzar la corrida (`--video-es`, `--video-pt`,
`--video-en`, o el campo `videos` de la API) y el producto usa esas.

Mientras no haya ni archivo ni URL, los mensajes **no mencionan ningún video**:
no se promete algo que no existe.

Los tres `demo.mp4` actuales los produce `python3 -m marketing.generar_video`:
capturas de la aplicación real corriendo en cada idioma, placas con la marca
que corresponde (MV Cliente IA en es/pt, MV SearchCostumer AI en inglés) y
locución generada en el idioma del receptor. Si hay que cambiar una escena o
un texto, se cambia el generador y se regenera — no se editan los videos a
mano, que a la primera corrección quedan desincronizados. Un video grabado
"de verdad" (con voz humana) puede reemplazar a cualquiera de los tres cuando
exista: mismo nombre de archivo y listo.
