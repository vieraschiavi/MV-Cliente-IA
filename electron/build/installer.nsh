; MV Cliente IA · retoques del instalador NSIS
; =============================================================================
; electron-builder arma el instalador; esto cambia UNA cosa concreta:
;
;   El instalador asistido de electron-builder muestra siempre la pantalla
;   "¿para quién instalar?" con dos opciones. Elegir "para todos los usuarios"
;   pide UAC e instala en C:\Program Files — y ahí el programa queda clavado en
;   C: para siempre: esa carpeta no es escribible por el usuario, así que
;   `dirDatos()` (electron/main.js) no puede guardar al lado de la app y todo
;   se va a %LOCALAPPDATA%, otra vez en C:.
;
;   Este producto está pensado para vivir en el disco que el usuario elija (la
;   landing lo promete y la edición portable ya lo cumple). Así que la pantalla
;   se saca: la instalación es SIEMPRE por usuario, sin UAC, y la única
;   decisión que queda es la que importa — en qué carpeta y en qué disco.
;
; `customInstallMode` es el punto de extensión oficial de la plantilla
; (templates/nsis/multiUserUi.nsh): poniendo $isForceCurrentInstall en 1, el
; `Abort` de esa pantalla la saltea y fija el modo por usuario.
;
; Lo que NO se toca: la página de directorio sigue existiendo tal cual, con su
; botón "Examinar…". Acá sólo se quita la bifurcación que llevaba a C:.

!macro customInstallMode
  ; 1 = instalar sólo para el usuario actual, sin preguntar y sin elevar.
  StrCpy $isForceCurrentInstall "1"
!macroend

; -----------------------------------------------------------------------------
; "No se puede cerrar MV Cliente IA. Por favor cierra la aplicación
; manualmente y haz clic en reintentar para continuar."
;
; Ese diálogo es de electron-builder (templates/nsis/include/
; allowOnlyOneInstallerInstance.nsh, mensaje `appCannotBeClosed`) y lo dispara
; SU chequeo de "¿está la app corriendo?" — que busca UN SOLO nombre de
; ejecutable: `MV Cliente IA.exe`, el de Electron. Ese chequeo NUNCA supo del
; motor (`MVClienteIA.exe`, el backend de FastAPI que `electron/main.js`
; levanta como proceso hijo en `resources\backend\`) porque para
; electron-builder ese archivo es un recurso más, no "la app".
;
; Ahí está el agujero: si Windows mata al padre de un golpe —que es
; exactamente lo que hace esa misma plantilla cuando, tras un par de
; reintentos, pasa a `taskkill /F` sobre `MV Cliente IA.exe`— el kill es un
; `TerminateProcess` a nivel de sistema operativo. Ese kill no dispara
; `before-quit` en Electron (ahí es donde `main.js` mata al motor con
; `backend.kill()`): a ese evento nunca lo llama nadie porque el proceso
; entero desaparece de un golpe. El motor queda HUÉRFANO, sigue corriendo, y
; sigue teniendo abiertos justo los archivos que el instalador necesita
; sobrescribir un paso más adelante (`resources\backend\MVClienteIA.exe` y
; sus DLL). El diálogo dice el nombre de la app, pero lo que de verdad sigue
; vivo — e invisible para ese chequeo — es el motor.
;
; La solución no es tocar el chequeo de electron-builder (funciona bien para
; lo que conoce: reintenta, escala a force-kill, y recién ahí avisa). Es
; matar al motor ACÁ, en `customInit` — el primer punto de extensión que
; corre la plantilla, antes de ese chequeo, antes de desinstalar la versión
; vieja y antes de copiar los archivos nuevos — así ningún paso posterior se
; encuentra con un motor todavía abierto, venga de esta instalación o de una
; sesión anterior que quedó a medio cerrar.
!macro customInit
  DetailPrint "Cerrando el motor de MV Cliente IA si estuviera abierto…"
  ; /T también mata lo que el motor haya podido lanzar (no lanza nada hoy,
  ; pero un backend sin ventana no tiene a quién pedirle que cierre solo:
  ; force-kill directo es lo único que tiene sentido acá).
  nsExec::Exec 'taskkill /F /T /IM "MVClienteIA.exe"'
  Pop $0
!macroend

; Mismo motivo que `customInit` de arriba, para cuando se desinstala directo
; (Panel de control → Desinstalar) en vez de a través de una instalación
; nueva: el desinstalador viejo va a intentar borrar `MVClienteIA.exe` más
; adelante, y si el motor sigue vivo el borrado falla de la misma manera.
!macro customUnInit
  DetailPrint "Cerrando el motor de MV Cliente IA si estuviera abierto…"
  nsExec::Exec 'taskkill /F /T /IM "MVClienteIA.exe"'
  Pop $0
!macroend
