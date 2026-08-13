@echo off
REM ===================================================================
REM  MV Cliente IA · descarga el instalador de Windows
REM
REM  Doble click y listo. Baja el .exe de la Release, comprueba el
REM  SHA-256 contra el que quedó versionado en esta carpeta y lo abre.
REM
REM  Por que un descargador y no el .exe adentro del repo: el instalador
REM  pesa ~95 MB y el ZIP portable ~126 MB. GitHub RECHAZA archivos de
REM  mas de 100 MB, y cada version quedaria para siempre en el historial
REM  — el repo pasaria de 40 MB a varios GB en un mes de trabajo. Los
REM  binarios viven en la Release, que es el lugar hecho para eso; aca
REM  quedan los hashes, que ocupan 89 bytes y sirven para verificar.
REM ===================================================================
setlocal
chcp 65001 >nul 2>&1

set "REPO=vieraschiavi/MV-Cliente-IA"
set "EDICION=%~1"
if "%EDICION%"=="" set "EDICION=demo"

REM Dos vias para lo mismo: el instalador .exe de siempre, y la edicion BAT
REM para las empresas donde no se pueden abrir programas descargados.
if /i "%EDICION%"=="demo"        set "ARCHIVO=MVClienteIA_Setup_demo.exe"
if /i "%EDICION%"=="cliente"     set "ARCHIVO=MVClienteIA_Setup.exe"
if /i "%EDICION%"=="bat"         set "ARCHIVO=MVClienteIA_BAT_demo.zip"
if /i "%EDICION%"=="bat-cliente" set "ARCHIVO=MVClienteIA_BAT_cliente.zip"

REM La edicion owner ya no se construye ni se publica: lleva el permiso
REM adentro del .exe y este repositorio es PUBLICO. Se avisa en vez de
REM mandar a autenticarse con gh contra una Release que no existe.
if /i "%EDICION%"=="owner" (
  echo   La edicion owner no se publica: este repositorio es publico y ese
  echo   .exe abre sin clave y sin vencimiento.
  echo   En su lugar usa la edicion cliente con una clave a tu nombre:
  echo       Descargar.cmd cliente
  pause
  exit /b 1
)

if not defined ARCHIVO (
  echo Edicion desconocida: %EDICION%
  echo.
  echo Uso:
  echo   Descargar.cmd              instalador .exe, prueba de 14 dias
  echo   Descargar.cmd cliente      instalador .exe, version comprada
  echo   Descargar.cmd bat          SIN .exe, prueba de 14 dias
  echo   Descargar.cmd bat-cliente  SIN .exe, version comprada
  pause
  exit /b 1
)

echo.
echo   MV Cliente IA - edicion %EDICION%
echo   Archivo: %ARCHIVO%
echo.

set "URL=https://github.com/%REPO%/releases/latest/download/%ARCHIVO%"
echo   Bajando de %URL%
powershell -NoProfile -Command ^
  "$ProgressPreference='SilentlyContinue';" ^
  "try { Invoke-WebRequest -Uri '%URL%' -OutFile '%~dp0%ARCHIVO%' -UseBasicParsing }" ^
  "catch { Write-Host ''; Write-Host '  No se pudo bajar: ' $_.Exception.Message; exit 1 }"
if errorlevel 1 goto :error

:verificar
REM Los hashes viven en CLIENTE\ (esquema de MV Agendate IA: lo que baja quien
REM compra va separado de lo del dueno). Se mira ahi y, por compatibilidad con
REM copias viejas de esta carpeta, tambien al lado de este .cmd.
set "HASH=%~dp0CLIENTE\%ARCHIVO%.sha256"
if not exist "%HASH%" set "HASH=%~dp0%ARCHIVO%.sha256"
if not exist "%HASH%" (
  REM Antes esto seguia de largo y abria el instalador igual. Un control de
  REM integridad que se saltea solo cuando falta su insumo no es un control:
  REM justo cuando no se puede verificar es cuando NO hay que ejecutar.
  echo.
  echo   [X] No encontre el .sha256 para comprobar la descarga.
  echo.
  echo       El archivo quedo bajado en:
  echo         %~dp0%ARCHIVO%
  echo.
  echo       No lo abro sin verificarlo. Compara el hash a mano contra el
  echo       publicado en la Release y, si coincide, abrilo vos.
  echo.
  goto :error
)
echo   Verificando SHA-256...
powershell -NoProfile -Command ^
  "$esperado = (Get-Content '%HASH%' -Raw).Split()[0].Trim().ToLower();" ^
  "$real = (Get-FileHash '%~dp0%ARCHIVO%' -Algorithm SHA256).Hash.ToLower();" ^
  "if ($esperado -ne $real) { Write-Host ''; Write-Host '  ATENCION: el archivo NO coincide con el hash publicado.'; Write-Host ('  esperado: ' + $esperado); Write-Host ('  bajado:   ' + $real); Write-Host '  No lo ejecutes: volve a bajarlo.'; exit 1 }" ^
  "Write-Host '  SHA-256 correcto.'"
if errorlevel 1 goto :error

:abrir
echo.
echo   Listo: %~dp0%ARCHIVO%
REM La edicion BAT es un ZIP, no un instalador: ejecutarlo abriria el visor
REM de archivos comprimidos y el usuario se quedaria mirando una carpeta
REM dentro del ZIP, que en Windows no se puede correr. Se descomprime y se
REM abre la carpeta de verdad.
if /i "%ARCHIVO:~-4%"==".zip" goto :descomprimir
echo   Abriendo el instalador...
start "" "%~dp0%ARCHIVO%"
exit /b 0

:descomprimir
echo   Descomprimiendo...
powershell -NoProfile -Command ^
  "Expand-Archive -Path '%~dp0%ARCHIVO%' -DestinationPath '%~dp0' -Force"
if errorlevel 1 goto :error
echo.
echo   Listo. Se abre la carpeta: hace doble click en MVClienteIA.bat
echo   Si lo queres dejar instalado con acceso directo, corre Instalar.bat
start "" "%~dp0MVClienteIA"
exit /b 0

:error
echo.
echo   Fallo la descarga o la verificacion.
pause
exit /b 1
