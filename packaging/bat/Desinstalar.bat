@echo off
REM ===================================================================
REM  MV Cliente IA - desinstalacion de la edicion BAT
REM
REM  Saca los accesos directos, la entrada de "Agregar o quitar
REM  programas" y las librerias que se instalaron la primera vez.
REM  Las corridas guardadas se preguntan aparte: son del usuario y
REM  borrarlas sin avisar seria perder su trabajo.
REM ===================================================================
setlocal EnableExtensions
cd /d "%~dp0"

set "ORIGEN=%~dp0"
REM La misma carpeta de datos que elige MVClienteIA.bat. Si no se respetara
REM MVCLIENTE_HOME, el desinstalador limpiaria una carpeta y el programa
REM habria estado usando otra: quedarian las librerias tiradas.
set "DATOS=%LOCALAPPDATA%\MVClienteIA"
if defined MVCLIENTE_HOME set "DATOS=%MVCLIENTE_HOME%"
set "CLAVE=HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\MVClienteIA"

echo.
echo   Desinstalar MV Cliente IA
echo   -------------------------
echo.
REM En modo automatico (MVCLIENTE_SIN_PAUSA, que usa el CI) se responde
REM que SI a desinstalar, pero que NO a las dos preguntas destructivas de
REM mas abajo: borrar las busquedas del usuario o su carpeta no es algo
REM que deba pasar sin que alguien lo pida en voz alta.
set "RESP=S"
if not defined MVCLIENTE_SIN_PAUSA set /p "RESP=Seguro que lo queres sacar? (S/N): "
if /i not "%RESP%"=="S" goto :cancelado

REM --- Accesos directos y Menu Inicio -------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$esc = Join-Path ([Environment]::GetFolderPath('Desktop')) 'MV Cliente IA.lnk';" ^
  "if (Test-Path $esc) { Remove-Item $esc -Force };" ^
  "$menu = Join-Path ([Environment]::GetFolderPath('Programs')) 'MV Cliente IA';" ^
  "if (Test-Path $menu) { Remove-Item $menu -Recurse -Force }" >nul 2>&1
echo   - accesos directos borrados

REM --- Agregar o quitar programas -----------------------------------
reg delete "%CLAVE%" /f >nul 2>&1
echo   - entrada de "Agregar o quitar programas" borrada

REM --- Librerias instaladas por MVClienteIA.bat ---------------------
if exist "%DATOS%\lib" rd /s /q "%DATOS%\lib" >nul 2>&1
if exist "%DATOS%\instalacion.log" del /q "%DATOS%\instalacion.log" >nul 2>&1
echo   - librerias borradas

REM --- Corridas guardadas: se pregunta ------------------------------
if not exist "%DATOS%\corridas" goto :carpeta
echo.
echo   Quedan tus busquedas guardadas en:
echo     %DATOS%\corridas
set "RESP=N"
if not defined MVCLIENTE_SIN_PAUSA set /p "RESP=Borrarlas tambien? (S/N): "
if /i "%RESP%"=="S" rd /s /q "%DATOS%\corridas" >nul 2>&1
if /i "%RESP%"=="S" echo   - busquedas borradas

:carpeta
REM --- La carpeta del programa --------------------------------------
REM Se borra a si misma con un cmd suelto que espera a que este archivo
REM termine; Windows no deja borrar la carpeta desde la que corre.
REM Los dos "if exist" son un seguro: sin ellos, un Desinstalar.bat
REM copiado por error a otra carpeta se llevaria puesta esa carpeta.
if not exist "%ORIGEN%MVClienteIA.bat" goto :listo
if not exist "%ORIGEN%packaging\lanzador_escritorio.py" goto :listo
echo.
echo   Carpeta del programa:
echo     %ORIGEN%
set "RESP=N"
if not defined MVCLIENTE_SIN_PAUSA set /p "RESP=Borrar tambien esta carpeta? (S/N): "
if /i not "%RESP%"=="S" goto :listo
echo   - se borrara al cerrarse esta ventana
start "" /min cmd /c "timeout /t 3 /nobreak >nul & rd /s /q ""%ORIGEN%"""
echo.
echo   Listo. MV Cliente IA fue desinstalado.
exit /b 0

:listo
echo.
echo   Listo. MV Cliente IA fue desinstalado.
if exist "%ORIGEN%MVClienteIA.bat" echo   Podes borrar esta carpeta cuando quieras: %ORIGEN%
echo.
call :pausa
exit /b 0

:cancelado
echo.
echo   Cancelado. No se toco nada.
echo.
call :pausa
exit /b 1

:pausa
if defined MVCLIENTE_SIN_PAUSA goto :eof
pause
goto :eof
