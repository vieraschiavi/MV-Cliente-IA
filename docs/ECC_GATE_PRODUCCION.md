# MV Cliente IA — Gate de producción ECC

> Puntaje bajo la rúbrica de `.claude/skills/ecc/SKILL.md` (ECC v2.2.0,
> skill `production-audit`). **Evidencia ejecutada o no cuenta.**

**Veredicto: 87/100 → 9/10. Sin bloqueantes. Suite grande y verde, linter
limpio, health check presente y cero secretos versionados.**

## Evidencia ejecutada

| Verificación | Comando | Resultado |
|---|---|---|
| Linter | `ruff check .` | ✅ `All checks passed!` |
| Suite Python | `python3 -m pytest -q tests/` | ✅ **496 tests, 0 fallas** |
| Health check | `/api/salud` en el backend | ✅ presente |
| Secretos versionados | `git ls-files \| grep -E '\.env$\|\.pem\|\.keystore'` | ✅ ninguno |

## Por qué 9 y no 10

Ningún tope duro aplica. Lo que no pude verificar desde acá:

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

Antes de cada push: `ruff check . && python -m pytest -q tests/`. Antes de un
release, además el build del frontend y el humo de la ventana.
