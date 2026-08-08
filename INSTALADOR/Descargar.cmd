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

if /i "%EDICION%"=="demo"    set "ARCHIVO=MVClienteIA_Setup_demo.exe"
if /i "%EDICION%"=="cliente" set "ARCHIVO=MVClienteIA_Setup.exe"

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
  echo Uso:  Descargar.cmd [demo^|cliente]
  pause
  exit /b 1
)

echo.
echo   MV Cliente IA — edicion %EDICION%
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
if not exist "%~dp0%ARCHIVO%.sha256" (
  echo   Sin .sha256 versionado para comparar; se salta la verificacion.
  goto :abrir
)
echo   Verificando SHA-256...
powershell -NoProfile -Command ^
  "$esperado = (Get-Content '%~dp0%ARCHIVO%.sha256' -Raw).Split()[0].Trim().ToLower();" ^
  "$real = (Get-FileHash '%~dp0%ARCHIVO%' -Algorithm SHA256).Hash.ToLower();" ^
  "if ($esperado -ne $real) { Write-Host ''; Write-Host '  ATENCION: el archivo NO coincide con el hash publicado.'; Write-Host ('  esperado: ' + $esperado); Write-Host ('  bajado:   ' + $real); Write-Host '  No lo ejecutes: volve a bajarlo.'; exit 1 }" ^
  "Write-Host '  SHA-256 correcto.'"
if errorlevel 1 goto :error

:abrir
echo.
echo   Listo: %~dp0%ARCHIVO%
echo   Abriendo el instalador...
start "" "%~dp0%ARCHIVO%"
exit /b 0

:error
echo.
echo   Fallo la descarga o la verificacion.
pause
exit /b 1
