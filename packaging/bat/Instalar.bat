@echo off
REM ===================================================================
REM  MV Cliente IA - instalacion de la edicion BAT
REM
REM  Deja lo mismo que el instalador .exe, sin ser un .exe:
REM    - acceso directo en el Escritorio
REM    - entrada en el Menu Inicio
REM    - entrada en "Agregar o quitar programas", con desinstalador
REM
REM  Todo por usuario (HKCU): no pide permisos de administrador y no
REM  toca nada de las otras cuentas de la maquina.
REM
REM  Los accesos directos se crean con PowerShell -Command, no con un
REM  .ps1: la ExecutionPolicy restringida bloquea los archivos .ps1
REM  pero no los comandos sueltos, asi que esto anda igual en una
REM  maquina con las politicas apretadas.
REM ===================================================================
setlocal EnableExtensions
cd /d "%~dp0"

set "NOMBRE=MV Cliente IA"
set "VERSION=@VERSION@"
set "EDICION=@EDICION@"
set "ORIGEN=%~dp0"
set "DATOS=%LOCALAPPDATA%\MVClienteIA"
set "CLAVE=HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\MVClienteIA"

echo.
echo   Instalando %NOMBRE% %VERSION% (edicion %EDICION%)
echo   ------------------------------------------------
echo.

if not exist "%ORIGEN%MVClienteIA.bat" (
  echo   ERROR: Instalar.bat tiene que quedar en la MISMA carpeta que
  echo   MVClienteIA.bat. Descomprimi el ZIP entero y volve a probar.
  echo.
  call :pausa
  exit /b 1
)

REM --- Accesos directos --------------------------------------------
REM El Escritorio se pregunta al sistema en vez de asumir %USERPROFILE%\Desktop:
REM con OneDrive o con Windows en otro idioma esa carpeta no esta ahi.
set "ICONO=%ORIGEN%assets\mv.ico"
if not exist "%ICONO%" set "ICONO=%SystemRoot%\System32\shell32.dll"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$esc = [Environment]::GetFolderPath('Desktop');" ^
  "$menu = Join-Path ([Environment]::GetFolderPath('Programs')) 'MV Cliente IA';" ^
  "New-Item -ItemType Directory -Force -Path $menu | Out-Null;" ^
  "foreach ($d in @($esc, $menu)) {" ^
  "  $l = $ws.CreateShortcut((Join-Path $d 'MV Cliente IA.lnk'));" ^
  "  $l.TargetPath = '%ORIGEN%MVClienteIA.bat';" ^
  "  $l.WorkingDirectory = '%ORIGEN%';" ^
  "  $l.IconLocation = '%ICONO%';" ^
  "  $l.Description = 'MV Cliente IA - encontra tus proximos clientes';" ^
  "  $l.Save() };" ^
  "$l = $ws.CreateShortcut((Join-Path $menu 'Desinstalar MV Cliente IA.lnk'));" ^
  "$l.TargetPath = '%ORIGEN%Desinstalar.bat';" ^
  "$l.WorkingDirectory = '%ORIGEN%';" ^
  "$l.Save()"
if errorlevel 1 goto :fallo

echo   - acceso directo en el Escritorio
echo   - entrada en el Menu Inicio

REM --- Agregar o quitar programas -----------------------------------
reg add "%CLAVE%" /v DisplayName     /t REG_SZ /d "%NOMBRE%"            /f >nul
reg add "%CLAVE%" /v DisplayVersion  /t REG_SZ /d "%VERSION%"           /f >nul
reg add "%CLAVE%" /v Publisher       /t REG_SZ /d "MV Cliente IA"       /f >nul
reg add "%CLAVE%" /v DisplayIcon     /t REG_SZ /d "%ICONO%"             /f >nul
reg add "%CLAVE%" /v InstallLocation /t REG_SZ /d "%ORIGEN%"            /f >nul
reg add "%CLAVE%" /v UninstallString /t REG_SZ /d "\"%ORIGEN%Desinstalar.bat\"" /f >nul
reg add "%CLAVE%" /v NoModify        /t REG_DWORD /d 1                  /f >nul
reg add "%CLAVE%" /v NoRepair        /t REG_DWORD /d 1                  /f >nul
if errorlevel 1 goto :fallo
echo   - entrada en "Agregar o quitar programas"

echo.
echo   Listo. Abrilo desde el Escritorio o desde el Menu Inicio.
echo   Para sacarlo: "Agregar o quitar programas", o Desinstalar.bat.
echo.
call :pausa
exit /b 0

:fallo
echo.
echo   No se pudieron crear los accesos directos.
echo   El programa igual funciona: abri MVClienteIA.bat directamente.
echo.
call :pausa
exit /b 1

:pausa
REM MVCLIENTE_SIN_PAUSA la define el CI, que instala y desinstala de
REM verdad para comprobar que los accesos directos quedan bien. Sin esto
REM el "Presione una tecla" lo dejaria esperando para siempre.
if defined MVCLIENTE_SIN_PAUSA goto :eof
pause
goto :eof
