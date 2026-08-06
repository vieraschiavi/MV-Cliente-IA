# El recuadro con tu cara en los reels

Los reels que funcionan en Instagram y TikTok tienen a una persona hablando en
un recuadro: es lo que hace que se miren. Eso no lo genera el código — hace
falta una cara. Poné acá tu clip y todos los reels futuros lo llevan:

```
marketing/presentador/es.mp4      ← el que se usa en español
marketing/presentador/pt.mp4      ← portugués (opcional)
marketing/presentador/en.mp4      ← inglés (opcional)
```

Si falta el del idioma, se usa `es.mp4`. Si no hay ninguno, el reel sale como
hasta ahora, sin recuadro: **no se inventa una cara**.

## Cómo grabarlo (5 minutos, con el teléfono)

1. Grabá **vertical u horizontal, da igual** — se reescala al recuadro.
2. **60 segundos alcanzan** para cualquiera de los tres reels (duran 43-51 s).
   El clip avanza a lo largo del reel en vez de reiniciarse en cada corte; si
   se termina antes, vuelve a empezar.
3. Hablá mirando a cámara. **No hace falta que digas el guion**: la locución
   la pone el generador con la voz neural. Vos ponés la cara y la energía —
   por eso el clip no lleva audio (se descarta).
4. Luz de frente, fondo tranquilo, y encuadre de pecho para arriba: el
   recuadro mide 260 px de ancho, una cara chica no se ve.

## Cómo se ve

El recuadro va abajo de todo y arriba del subtítulo, con borde verde de la
marca. Cuando hay presentador, la tarjeta con la captura de la app se achica
sola para dejarle lugar — si no, se pisaban.

## Si preferís un avatar de IA

Un clip hecho con HeyGen, Synthesia, D-ID o similar sirve igual: es un mp4
como cualquier otro. Lo generás en el servicio, lo bajás y lo dejás acá con el
nombre del idioma. El generador no distingue ni le importa.

Después: `python3 -m marketing.generar_reel`
