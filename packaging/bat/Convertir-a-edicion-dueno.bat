@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
title MV Cliente IA - pasar a edicion DUENO
cd /d "%~dp0"

REM ===================================================================
REM  Pasa una copia YA INSTALADA de MV Cliente IA a la edicion DUENO:
REM  sin clave de licencia y sin vencimiento.
REM
REM  COMO SE USA
REM    1. Doble clic. Nada mas.
REM    2. Si el programa estaba abierto, cerralo y volve a abrirlo.
REM
REM  A diferencia del conversor de MV Agendate IA, este NO hay que
REM  copiarlo a la carpeta del programa: la BUSCA solo. Mira, en este
REM  orden, el registro de Windows (donde el instalador anota adonde
REM  se instalo), las carpetas donde Windows instala por defecto, el
REM  destino real de los accesos directos del escritorio y del menu
REM  Inicio, y por ultimo la carpeta desde donde se lo ejecuto. Hace
REM  falta porque el instalador deja ELEGIR la carpeta
REM  (allowToChangeInstallationDirectory), asi que asumir una ruta fija
REM  era exactamente lo que fallaba.
REM
REM  Encuentra las tres formas de entrega:
REM    - Instalador .exe  -> el sello va en resources\backend\
REM    - Portable .zip    -> mismo formato que el instalador
REM    - Edicion BAT      -> el sello va en packaging\
REM
REM  QUE HACE POR DENTRO
REM    La edicion no vive en el registro ni en una licencia: es un
REM    archivo `edicion.json` adentro de la carpeta del programa que el
REM    motor lee al arrancar (cliente_ia/licencia.py). Este script lo
REM    reemplaza por el de la edicion dueno y deja una copia .original
REM    para poder volver atras corriendolo de nuevo.
REM
REM  NO REPARTAS ESTE ARCHIVO. Convierte cualquier copia instalada en
REM  la edicion completa: es la llave maestra de tu propio producto.
REM  Por eso pide tu codigo de dueno: si el archivo se filtra, sin ese
REM  codigo no sirve para nada. Y por eso se arma con
REM  `packaging/armar_owner.py` en tu maquina y no se versiona: este
REM  repositorio es publico.
REM ===================================================================

set "CODIGO_ESPERADO={{CODIGO_SHA256}}"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass -Command"

echo.
echo  ================================================
echo   MV Cliente IA - pasar a edicion DUENO
echo  ================================================
echo.

REM --- Buscar la instalacion -----------------------------------------
echo  [..] Buscando donde quedo instalado MV Cliente IA...
echo.

set "HALLAZGOS=%TEMP%\mvcliente_instalaciones.txt"
if exist "%HALLAZGOS%" del /q "%HALLAZGOS%" >nul 2>nul

%PS% ^
  "$ErrorActionPreference = 'SilentlyContinue';" ^
  "$c = New-Object System.Collections.Generic.List[string];" ^
  "foreach ($r in @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall'," ^
  "                 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall'," ^
  "                 'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall')) {" ^
  "  if (Test-Path $r) { Get-ChildItem $r | ForEach-Object {" ^
  "    $p = Get-ItemProperty $_.PSPath;" ^
  "    if ($p.DisplayName -like '*MV Cliente IA*' -and $p.InstallLocation) { $c.Add($p.InstallLocation) } } } };" ^
  "foreach ($b in @(\"$env:LOCALAPPDATA\Programs\", \"$env:ProgramFiles\", ${env:ProgramFiles(x86)}, \"$env:APPDATA\")) {" ^
  "  if ($b) { $c.Add((Join-Path $b 'MV Cliente IA')); $c.Add((Join-Path $b 'MVClienteIA')) } };" ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {" ^
  "  Get-ChildItem $d -Filter '*.lnk' -Recurse | Where-Object { $_.Name -like '*MV Cliente*' -or $_.Name -like '*MVCliente*' } |" ^
  "    ForEach-Object { $t = $ws.CreateShortcut($_.FullName).TargetPath;" ^
  "      if ($t) { $c.Add((Split-Path $t -Parent)) } } };" ^
  "$d = (Get-Location).Path; for ($i = 0; $i -lt 4 -and $d; $i++) { $c.Add($d); $d = Split-Path $d -Parent };" ^
  "$ok = New-Object System.Collections.Generic.List[string];" ^
  "foreach ($ruta in ($c | Select-Object -Unique)) {" ^
  "  if (-not (Test-Path $ruta)) { continue };" ^
  "  $sellos = @((Join-Path $ruta 'resources\backend'), (Join-Path $ruta 'packaging'));" ^
  "  foreach ($s in $sellos) {" ^
  "    $marca = if ($s -like '*backend') { Join-Path $s 'MVClienteIA.exe' } else { Join-Path $ruta 'MVClienteIA.bat' };" ^
  "    if ((Test-Path $s) -and (Test-Path $marca)) { $ok.Add($s) } } };" ^
  "$ok | Select-Object -Unique | Set-Content -LiteralPath '%HALLAZGOS%' -Encoding ascii"

if not exist "%HALLAZGOS%" goto :no_encontre
for /f "usebackq delims=" %%L in ("%HALLAZGOS%") do set "ENCONTRADO=1"
if not defined ENCONTRADO goto :no_encontre

echo  Instalaciones encontradas:
for /f "usebackq delims=" %%L in ("%HALLAZGOS%") do echo    - %%~dpL
echo.

REM --- Pedir el codigo de dueno --------------------------------------
REM Sin esto, el archivo filtrado destrabaria cualquier copia. Se compara
REM el SHA-256, asi que el codigo en si no viaja adentro del .bat.
if "%CODIGO_ESPERADO%"=="" goto :sin_hornear
set "CODIGO="
if not defined MVCLIENTE_SIN_PAUSA set /p "CODIGO=  Tu codigo de dueno: "
if defined MVCLIENTE_SIN_PAUSA set "CODIGO=%MVCLIENTE_CODIGO_DUENO%"
if not defined CODIGO goto :sin_codigo

for /f "usebackq delims=" %%H in (`%PS% ^
  "$b = [Text.Encoding]::UTF8.GetBytes('!CODIGO!');" ^
  "$h = [Security.Cryptography.SHA256]::Create().ComputeHash($b);" ^
  "-join ($h ^| ForEach-Object { $_.ToString('x2') })"`) do set "CODIGO_HASH=%%H"

if /i not "!CODIGO_HASH!"=="%CODIGO_ESPERADO%" goto :codigo_malo

REM --- Si ya esta en dueno, ofrecer volver atras (igual que Agendate) --
set "YA=1"
for /f "usebackq delims=" %%S in ("%HALLAZGOS%") do (
  findstr /c:"owner" "%%S\edicion.json" >nul 2>nul || set "YA="
)
if defined YA goto :ya_esta

REM --- Convertir ------------------------------------------------------
echo.
echo  [..] Escribiendo el sello de la edicion dueno...

%PS% ^
  "$ErrorActionPreference = 'Stop';" ^
  "$hechos = 0;" ^
  "foreach ($s in (Get-Content -LiteralPath '%HALLAZGOS%')) {" ^
  "  $sello = Join-Path $s 'edicion.json';" ^
  "  if ((Test-Path $sello) -and -not (Test-Path \"$sello.original\")) {" ^
  "    Copy-Item $sello \"$sello.original\" -Force };" ^
  "  Set-Content -LiteralPath $sello -Value '{\"edicion\":\"owner\"}' -Encoding ascii -NoNewline;" ^
  "  if ((Get-Content -LiteralPath $sello -Raw) -match 'owner') { $hechos++;" ^
  "    Write-Host ('  [OK] ' + $sello) } };" ^
  "if ($hechos -eq 0) { exit 1 }"

if errorlevel 1 goto :fallo

echo.
echo  [OK] Listo. Esta copia quedo en edicion DUENO.
echo.
echo       - No pide clave de licencia.
echo       - No tiene vencimiento.
echo.
echo  Si el programa estaba abierto, cerralo y volve a abrirlo: el
echo  motor lee el sello al arrancar.
echo.
echo  Para volver a la edicion normal, corre este mismo archivo otra vez.
echo.
del /q "%HALLAZGOS%" >nul 2>nul
call :pausa
exit /b 0

:ya_esta
echo  Esta copia YA esta en edicion dueno (sin clave ni vencimiento).
echo.
REM En el CI no hay nadie que conteste: la respuesta llega por
REM MVCLIENTE_REVERTIR, que es como se prueba la vuelta atras en Windows.
set "RESP=%MVCLIENTE_REVERTIR%"
if not defined MVCLIENTE_SIN_PAUSA set /p "RESP=  Queres volverla a la edicion normal? [s/N] "
if /i not "!RESP!"=="s" goto :sin_cambios

%PS% ^
  "$ErrorActionPreference = 'SilentlyContinue';" ^
  "$vueltos = 0;" ^
  "foreach ($s in (Get-Content -LiteralPath '%HALLAZGOS%')) {" ^
  "  $sello = Join-Path $s 'edicion.json';" ^
  "  if (Test-Path \"$sello.original\") {" ^
  "    Copy-Item \"$sello.original\" $sello -Force; $vueltos++;" ^
  "    Write-Host ('  [OK] ' + $sello) }" ^
  "  else { Write-Host ('  [!] sin copia .original: ' + $sello) } };" ^
  "if ($vueltos -eq 0) { exit 1 }"

if errorlevel 1 goto :sin_backup
echo.
echo  [OK] Volvio a la edicion que traia el instalador.
echo       Cerra y volve a abrir el programa.
echo.
del /q "%HALLAZGOS%" >nul 2>nul
call :pausa
exit /b 0

:sin_cambios
echo.
echo  No toque nada. Sigue en edicion dueno.
echo.
del /q "%HALLAZGOS%" >nul 2>nul
call :pausa
exit /b 0

:sin_backup
echo.
echo  [X] No encontre las copias .original, asi que no puedo revertir.
echo      Si necesitas la edicion con prueba, reinstala con el
echo      instalador normal.
echo.
del /q "%HALLAZGOS%" >nul 2>nul
call :pausa
exit /b 1

:no_encontre
echo  [X] No encontre ninguna instalacion de MV Cliente IA.
echo.
echo      Busque en el registro de Windows, en las carpetas donde
echo      Windows instala por defecto, en los accesos directos del
echo      escritorio y del menu Inicio, y en esta carpeta.
echo.
echo      Si lo instalaste en una carpeta rara, copia este archivo
echo      adentro de esa carpeta y volve a ejecutarlo.
echo.
echo      Para encontrarla: clic derecho en el acceso directo del
echo      escritorio y "Abrir ubicacion del archivo".
echo.
call :pausa
exit /b 1

:sin_hornear
echo  [X] Este archivo esta sin armar: le falta el codigo de dueno.
echo.
echo      Armalo en tu maquina con:
echo        python3 packaging/armar_owner.py --codigo TU-CODIGO
echo.
call :pausa
exit /b 1

:sin_codigo
echo.
echo  [X] Sin codigo no se convierte nada.
echo.
call :pausa
exit /b 1

:codigo_malo
echo.
echo  [X] Ese no es el codigo de dueno de esta copia.
echo.
echo      No se toco ningun archivo.
echo.
del /q "%HALLAZGOS%" >nul 2>nul
call :pausa
exit /b 1

:fallo
echo.
echo  [X] No pude escribir el sello.
echo.
echo      Suele ser una de estas:
echo        - El programa esta abierto: cerralo y proba de nuevo.
echo        - El antivirus bloquea la escritura en esa carpeta.
echo        - Se instalo en "Archivos de programa" y hace falta
echo          ejecutar este .bat como administrador
echo          (clic derecho - "Ejecutar como administrador").
echo.
del /q "%HALLAZGOS%" >nul 2>nul
call :pausa
exit /b 1

REM --- La pausa se saltea en el CI, que no tiene a nadie que apriete una
REM     tecla: sin esto el job se cuelga hasta que expira, y en verde.
:pausa
if defined MVCLIENTE_SIN_PAUSA goto :eof
pause
goto :eof
