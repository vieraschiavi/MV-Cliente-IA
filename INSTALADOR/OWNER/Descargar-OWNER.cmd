@echo off
REM ===================================================================
REM  MV Cliente IA - baja la EDICION DUENO (version completa)
REM
REM  Doble click y listo. Baja el instalador de la Release owner-latest,
REM  comprueba el SHA-256 contra el que quedo versionado en esta carpeta
REM  y lo abre.
REM
REM  Uso:
REM    Descargar-OWNER.cmd            instalador .exe (por defecto)
REM    Descargar-OWNER.cmd portable   ZIP portable, sin instalar
REM
REM  Por que la Release y no el .exe adentro del repo: el portable pesa
REM  ~126 MB y GitHub RECHAZA archivos de mas de 100 MB, asi que no
REM  entra; y el instalador (~95 MB) quedaria en el historial de git
REM  para siempre, en cada version. Ver README.md de esta carpeta.
REM
REM  OJO: este repositorio es PUBLICO, asi que esa Release la puede bajar
REM  cualquiera. Es una decision tomada a conciencia para poder probar la
REM  version completa; el README explica como cerrarla.
REM ===================================================================
setlocal
chcp 65001 >nul 2>&1

set "REPO=vieraschiavi/MV-Cliente-IA"
set "TAG=owner-latest"
set "QUE=%~1"
if "%QUE%"=="" set "QUE=exe"

if /i "%QUE%"=="exe"      set "ARCHIVO=MVClienteIA_Setup_owner.exe"
if /i "%QUE%"=="portable" set "ARCHIVO=MVClienteIA_Portable_owner.zip"

if not defined ARCHIVO (
  echo Opcion desconocida: %QUE%
  echo.
  echo Uso:
  echo   Descargar-OWNER.cmd            instalador .exe
  echo   Descargar-OWNER.cmd portable   ZIP portable, sin instalar
  pause
  exit /b 1
)

echo.
echo   MV Cliente IA - EDICION DUENO (sin clave, sin vencimiento)
echo   Archivo: %ARCHIVO%
echo.

set "URL=https://github.com/%REPO%/releases/download/%TAG%/%ARCHIVO%"
echo   Bajando de %URL%
powershell -NoProfile -Command ^
  "$ProgressPreference='SilentlyContinue';" ^
  "try { Invoke-WebRequest -Uri '%URL%' -OutFile '%~dp0%ARCHIVO%' -UseBasicParsing }" ^
  "catch { Write-Host ''; Write-Host '  No se pudo bajar: ' $_.Exception.Message; exit 1 }"
if errorlevel 1 goto :error

REM Mismo criterio que Descargar.cmd: si NO se puede verificar, NO se abre.
REM Un control de integridad que se saltea solo cuando falta su insumo no es
REM un control.
set "HASH=%~dp0%ARCHIVO%.sha256"
if not exist "%HASH%" (
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

echo.
echo   Listo: %~dp0%ARCHIVO%
echo.

REM El portable es un ZIP: ejecutarlo abriria el visor de comprimidos y el
REM usuario se quedaria mirando una carpeta que Windows no puede correr. Se
REM descomprime y se abre la carpeta.
if /i "%QUE%"=="portable" (
  echo   Descomprimiendo...
  powershell -NoProfile -Command ^
    "Expand-Archive -LiteralPath '%~dp0%ARCHIVO%' -DestinationPath '%~dp0MVClienteIA_owner' -Force"
  echo   Abriendo la carpeta. Ejecuta MVClienteIA.exe adentro.
  start "" "%~dp0MVClienteIA_owner"
  exit /b 0
)

echo   Abriendo el instalador...
echo   Si Windows muestra "Windows protegio tu PC": Mas informacion -
echo   Ejecutar de todas formas. Es SmartScreen: el instalador todavia no
echo   tiene firma de codigo. El SHA-256 que se acaba de verificar es la
echo   comprobacion de que el archivo es el que compilo el CI.
echo.
start "" "%~dp0%ARCHIVO%"
exit /b 0

:error
echo.
pause
exit /b 1
