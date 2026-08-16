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
