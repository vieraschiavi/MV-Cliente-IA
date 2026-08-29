# MV Cliente IA — Gate de producción ECC

> Puntaje bajo la rúbrica de `.claude/skills/ecc/SKILL.md` (ECC v2.2.0,
> skill `production-audit`). **Evidencia ejecutada o no cuenta.**

**Veredicto: 79/100 → 8/10. Sale con salvedades. El código está sano —496
tests verdes, linter limpio, health check presente, cero secretos versionados—
pero el repositorio no tiene rama `main`: la rama por defecto es una rama de
trabajo, y eso frena la nota.**

## Evidencia ejecutada

| Verificación | Comando | Resultado |
|---|---|---|
| Linter | `ruff check .` | ✅ `All checks passed!` |
| Suite Python | `python3 -m pytest -q tests/` | ✅ **496 tests, 0 fallas** |
| Health check | `/api/salud` en el backend | ✅ presente |
| Secretos versionados | `git ls-files \| grep -E '\.env$\|\.pem\|\.keystore'` | ✅ ninguno |

## El tope: no hay rama `main`

La rama por defecto de este repositorio es `claude/replicate-explee-kobra-s9sx0s`
—una rama de trabajo—, y **`main` no existe**. Las únicas dos ramas del repo son
esa y la de este PR.

No es cosmético:

- **No hay línea estable.** Si esa rama se renombra o se borra, el producto se
  va con ella. El nombre además ata el repositorio a una tarea puntual que ya
  terminó.
- **Un runner de CI o un deploy que apunte a `main` no encuentra nada.**
- **Cualquiera que clone el repo aterriza en una rama de trabajo**, sin forma
  de saber si es la versión buena.

Arreglo: renombrar esa rama a `main` y ponerla como default en la
configuración del repositorio. Son cinco minutos y sube el puntaje a 9/10 sin
tocar una línea de código. Este PR se abre contra la rama por defecto actual
porque es la única base posible.

## Lo demás que falta para el 10

Ningún tope duro de seguridad aplica. Lo que no pude verificar desde acá:

1. **La corrida end-to-end de CI.** `ci.yml` tiene un paso "Corrida
   end-to-end" y un job de humo de la ventana Electron que no se corrieron
   en esta auditoría. Que 496 tests pasen no prueba que la app de escritorio
   abra — es exactamente el hueco que ese job de humo existe para tapar.
2. **El build del frontend.** `cd webapp/frontend && npm ci && npm run build`
   es un job aparte de CI y no se ejecutó acá.
3. **La instalación real en Windows.** Hay `build_windows.yml` y `apk.yml`,
   pero nadie corrió el instalador ni el APK en un dispositivo limpio dentro
   de esta auditoría. Es el primer contacto del cliente que paga.

## Arreglos de alto valor

1. Correr los tres jobs de arriba localmente antes de un release, no solo
   pytest.
2. Un humo post-deploy que verifique que la URL publicada responde.

## Próxima acción

Renombrar la rama por defecto a `main` — es el arreglo de mayor impacto y el
más barato. Después, antes de cada push: `ruff check . && python -m pytest -q tests/`. Antes de un
release, además el build del frontend y el humo de la ventana.
