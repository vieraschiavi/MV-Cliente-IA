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

> Estado actual: los tres idiomas sirven el **mismo** video (la demo real de
> MV Kobra AI, en español). Es a propósito — un video real en español le gana a
> un cartel de "no publicado" — pero cuando tengas las versiones en portugués
> e inglés, reemplazá `pt/demo.mp4` y `en/demo.mp4` y listo.
