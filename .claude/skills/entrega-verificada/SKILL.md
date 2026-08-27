---
name: entrega-verificada
description: >
  Protocolo de auditoría final para certificar que un programa/web/plataforma de pago está
  100% listo para producción, en todos los aspectos: seguridad del camino de pago, hardening
  de infraestructura, correctitud de backend, frontend/UI/i18n/imágenes, contenido multimedia
  por idioma, y regresión de las reglas de negocio propias del proyecto (las de su CLAUDE.md
  o equivalente). Corre una auditoría exhaustiva con sub-agentes en paralelo, uno por
  dimensión, y verifica cada hallazgo adversarialmente antes de reportarlo — nunca confía en
  la palabra de un solo agente. ACTIVAR con "/entrega-verificada", "auditoría final",
  "certificar para producción", "revisar todo antes de lanzar", "plataforma de pago lista",
  "confirmar que se corrigieron todos los errores del proyecto", o pedidos equivalentes de
  verificación exhaustiva end-to-end antes de entregar o lanzar un producto.
---

# Entrega Verificada — auditoría final antes de producción

Protocolo genérico (sin hardcodear ningún proyecto puntual) para certificar, con evidencia
ejecutada y verificación adversarial, que un programa está listo para producción. Pensado
para plataformas que cobran dinero, pero aplica a cualquier entrega donde "declarar
terminado" tiene costo real si está mal.

No reemplaza `security-review` ni `code-review`: los orquesta como dimensiones dentro de un
protocolo más amplio, con un paso que los otros dos no tienen — verificación adversarial de
cada hallazgo por un segundo agente que no vio el primero, antes de que el hallazgo cuente.

## Paso 0 — Relevar el proyecto (una vez, manual, rápido)

Antes de auditar, juntar el contexto que cada dimensión va a necesitar, para no obligar a
cada sub-agente a redescubrirlo desde cero:

- Stack real (lenguajes, frameworks, dónde corre: serverless sin disco vs instalado con
  disco — importa mucho para bugs de estado).
- Reglas de negocio propias que no se pueden romper (`CLAUDE.md` del repo si existe, o
  documento equivalente).
- Bugs históricos ya encontrados y corregidos (para no reportarlos de nuevo como hallazgo
  "nuevo", y para pedirle a cada dimensión que confirme específicamente que no volvieron).
- Dónde está el camino de dinero, si el proyecto cobra: qué endpoint recibe el pago, qué
  emite a cambio (licencia, acceso, producto), y con qué secreto se firma cada cosa.

## Paso 1 — Dimensiones (piso mínimo; adaptar al proyecto real)

1. **Seguridad del camino de pago** (si el proyecto cobra) — falsificación de pago, montos
   manipulables, secretos que se filtran por logs o respuestas, ausencia de rate-limiting.
2. **Hardening de infraestructura** — fallos de red sin manejar, inyección en claves/queries
   armadas con datos de usuario, tokens/HMAC reusados entre propósitos distintos, cupos
   gratis con bypass más barato que cambiar de IP.
3. **Correctitud de backend** — sentinels ambiguos (`None`/`0`/`""` usados para dos
   significados distintos), estado en memoria de proceso que no sobrevive en serverless,
   excepciones a mitad de un flujo largo que se tragan en silencio.
4. **Frontend/UI** — completitud de i18n (las mismas claves en todos los idiomas, ninguna
   interpolación rota), imágenes con texto que no se solape con el fondo y que se autoajuste
   al marco del contenido, accesibilidad básica, cero mezcla de idiomas en una misma
   pantalla.
5. **Multimedia por idioma** (si el producto usa video/audio localizado) — contenido y voz
   realmente distintos por idioma, no el mismo audio reetiquetado; declarar explícitamente el
   límite de lo que un agente de texto puede verificar (no transcribe habla, no juzga acento).
6. **Regresión de reglas de negocio propias** — cada regla del documento de reglas del
   proyecto tiene que tener un test que la proteja HOY, no sólo un comentario o una promesa.

Sumar o sacar dimensiones según lo que el proyecto realmente tenga (sin pagos, sacar la 1;
sin video, sacar la 5; con auth de usuarios, sumar una dimensión de sesiones/permisos; con
base de datos compartida, sumar una de integridad de datos).

## Paso 2 — Un sub-agente por dimensión, en paralelo

Usar el orquestador de sub-agentes disponible (p. ej. la herramienta Workflow) para correr
las N dimensiones en simultáneo, cada una con:

- El contexto del Paso 0 embebido directamente en el prompt — no asumir que el sub-agente lo
  va a ir a buscar solo; darle archivo:línea concreto de dónde mirar cuando se pueda.
- Instrucción explícita de devolver `findings: []` si de verdad no encuentra nada: en un
  proyecto maduro, una dimensión sin hallazgos es un resultado válido, no un fallo del
  agente ni señal de que revisó poco.
- Salida en un schema estructurado (JSON: título, archivo, línea, severidad, resumen,
  evidencia, fix sugerido) para poder verificar cada ítem por separado después.

## Paso 3 — Verificación adversarial (nunca saltear)

Cada hallazgo del Paso 2 se manda a un SEGUNDO agente independiente, que no ve la
conversación del primero, con instrucción explícita de tratar de refutarlo:

- Si un test existente ya cubre el hallazgo y pasa, es falso positivo.
- Si la evidencia citada no reproduce lo que dice, es falso positivo.
- Si es una opinión de estilo sin impacto concreto de seguridad/correctitud/negocio, es falso
  positivo.
- Ante la duda genuina, el veredicto por defecto es "no confirmado": se prefiere perder un
  hallazgo dudoso a inflar el reporte con ruido.

Sólo lo que sobrevive esta verificación entra al reporte final como confirmado.

## Paso 4 — Crítico de completitud

Un último agente mira la lista de hallazgos CONFIRMADOS (no los descartados) y pregunta qué
modalidad de revisión no se corrió y debería haberse corrido para este tipo de producto
(dependencias con CVEs conocidos, prueba contra el proveedor de pago real y no simulado,
CORS/permisos, reuso de identificadores, verificación visual real de cada imagen en vez de
sólo confirmar que existe). Este paso no vuelve a auditar — señala huecos de cobertura para
una próxima vuelta, y se reportan como tales, no como hallazgos confirmados.

## Paso 5 — Fixes, uno por vez, nunca en paralelo

Los hallazgos confirmados con fix aplicable se corrigen SECUENCIALMENTE: agentes en paralelo
escribiendo al mismo repo se pisan cambios entre sí. Después de cada fix: correr la suite de
tests y el linter del proyecto. Nunca declarar un hallazgo resuelto sin tests en verde.

## Paso 6 — Reporte final

Documento (o actualización del documento de estado del proyecto) con:

- Qué se auditó (las N dimensiones) y con qué evidencia — comandos corridos, no
  afirmaciones.
- Qué se encontró, qué de eso se confirmó, qué de eso se arregló y con qué commit.
- Qué NO se pudo verificar y por qué — límites honestos: un agente de texto no transcribe
  audio, no accede a un dashboard privado del proveedor de pago, no ejecuta un pago real con
  tarjeta verdadera, etc.
- Los huecos de cobertura que señaló el crítico de completitud, para la próxima vuelta.

## Reglas

- Nunca declarar "100% verificado" sin la verificación adversarial del Paso 3 — el primer
  agente que audita siempre tiene falsos positivos y falsos negativos.
- Nunca aplicar fixes de hallazgos distintos en paralelo sobre el mismo repo.
- Nunca inventar que se corrió un comando: si algo no se pudo ejecutar (falta de acceso,
  límite de la herramienta, servicio externo no simulable), decirlo explícito en el reporte
  en vez de asumir que está bien.
- Escalar el número de dimensiones y de hallazgos verificados al tamaño real del riesgo: una
  landing sin pagos no necesita la misma profundidad que una plataforma que cobra tarjetas.
- Deferencia a skills más específicos que ya cubran una dimensión puntual (p. ej. un skill de
  seguridad propio del usuario): este protocolo los orquesta, no los reemplaza.
