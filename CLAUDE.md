# CLAUDE.md — MV Cliente IA

> Contexto persistente para Claude Code. Leelo al iniciar cada sesión.

## Qué es
**MV Cliente IA** replica el flujo *auto-GTM* de explee.com sobre el stack y el
diseño de **MV Kobra AI**: se le pasa la URL de un producto y recorre seis fases
—investigar, competencia, campañas, prospectos, decisores, correos— priorizando
**Uruguay → LATAM → resto del mundo** y escribiendo en **es/pt/en**.

## Stack
- **Motor:** Python 3.11, sólo biblioteca estándar (`cliente_ia/`)
- **Backend:** FastAPI + uvicorn (`webapp/backend/api.py`)
- **Frontend:** React 18 + Vite + react-router (HashRouter) (`webapp/frontend/`)
- **PC:** Electron (`electron/`) · **Android:** Capacitor (`android/`)
- **Export:** openpyxl · **Tests:** pytest · **Lint:** ruff

## Comandos
| Acción | Comando |
|--------|---------|
| Instalar | `pip install -r requirements-dev.txt` |
| Pipeline | `python3 -m cliente_ia.pipeline mvkobranzaia.com --modo demo` |
| **Tests** | `python3 -m pytest -q tests/` |
| **Linter** | `ruff check .` |
| Backend | `python3 -m uvicorn webapp.backend.api:app --port 8810` |
| Build web | `npm run build:web` |
| APK | `npm run apk:debug` (necesita `ANDROID_HOME`) |
| Landing | `python3 -m marketing.generar_landing` |

## Reglas que no se rompen
1. **Uruguay primero.** El orden vive en `geo.py` (pesos 1.00 / 0.72 / 0.45) y en
   `scoring.ordenar_prospectos`, que ordena **por ola antes que por puntaje**. Si
   tocás pesos, corré `tests/test_scoring.py` — hay un test que existe sólo para
   impedir que un prospecto del exterior se cuele delante de uno uruguayo.
2. **El idioma del correo lo decide el país del decisor**, no la interfaz. Todo
   texto que entre a un correo tiene que existir en los tres idiomas
   (`Empresa.textos`, `Prospecto.dolor`). Regresión ya arreglada una vez: los
   correos en PT/EN llevaban un párrafo en español.
3. **Los datos sintéticos se dicen sintéticos.** `sintetico=True` viaja en cada
   registro del proveedor demo, la interfaz muestra el cartel y el CSV lleva la
   columna. Nunca generar personas reales con datos de contacto.
4. **El proveedor LLM no hace la fase 5.** Propone organizaciones, nunca
   personas. Está documentado en `proveedores/llm.py` y es a propósito.
5. **Determinismo del modo demo.** La semilla sale del dominio. Si dejás de ser
   determinista, se cae medio `tests/test_pipeline.py`.

## Convenciones
- Español en el dominio y en los nombres de módulo, igual que MV Kobra AI.
- Comentarios que expliquen **por qué**, no qué. Los que están dicen qué falló
  antes — no los borres al refactorizar.
- El tema visual sale de `webapp/frontend/src/theme.css`, que son los tokens de
  Kobra. No inventar colores nuevos.
- Un solo CSS para web, PC y APK: el modo móvil es un `@media (max-width: 860px)`
  del mismo archivo, no una hoja aparte.

## Flujo de trabajo
1. Cambio acotado.
2. `ruff check .` y `python3 -m pytest -q tests/`. Nunca declarar algo listo sin
   tests verdes.
3. Si tocaste el frontend: `npm run build:web` y probalo de verdad en el
   navegador (Playwright sirve).
4. Si tocaste la landing: regenerarla, no editar los tres HTML a mano.

## Do / Don't
- ✅ Tests antes de commitear · ✅ Datos sintéticos marcados · ✅ Semilla fija.
- ❌ `rm -rf` ni `git push --force` · ❌ Leer o loguear secretos · ❌ Listas de
  personas reales · ❌ Editar `landing/*/index.html` a mano.
