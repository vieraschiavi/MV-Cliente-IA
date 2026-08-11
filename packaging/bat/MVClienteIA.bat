@echo off
REM ===================================================================
REM  MV Cliente IA - edicion BAT (sin ningun .exe propio)
REM
REM  Para las empresas que no dejan ejecutar programas descargados.
REM  Corre EXACTAMENTE el mismo producto que el instalador de Windows
REM  -el motor con la interfaz React- pero en el navegador que ya
REM  tenes, usando el Python que ya esta instalado en la maquina.
REM
REM  POR QUE NO ARMA UN ENTORNO VIRTUAL (venv):
REM  crear un venv COPIA python.exe a una carpeta del usuario, y la
REM  regla tipica de AppLocker/SRP es justamente "no ejecutar .exe
REM  desde carpetas donde el usuario puede escribir". O sea: el venv
REM  rompe en la misma clase de maquina para la que existe esta
REM  edicion. En vez de eso las dependencias se instalan con
REM  "pip --target" en una carpeta de datos y se corre el python.exe
REM  original, que ya esta en una ruta permitida.
REM
REM  Sin acentos a proposito: la consola de Windows los rompe segun la
REM  pagina de codigos y quedan mensajes ilegibles.
REM ===================================================================
setlocal EnableExtensions
title MV Cliente IA
cd /d "%~dp0"

set "DATOS=%LOCALAPPDATA%\MVClienteIA"
if defined MVCLIENTE_HOME set "DATOS=%MVCLIENTE_HOME%"
set "LIBS=%DATOS%\lib"
set "REGISTRO=%DATOS%\instalacion.log"

REM Las corridas van a la carpeta del usuario, no al lado del programa.
REM Sin esto el motor escribiria en su propia carpeta: revienta si el ZIP
REM se descomprimio en un lugar de solo lectura, y ademas el
REM desinstalador no sabria donde quedaron las busquedas guardadas.
if not defined MVCLIENTE_DIR_DATOS set "MVCLIENTE_DIR_DATOS=%DATOS%"

echo.
echo   MV Cliente IA
echo   =============
echo.

REM --- 1. Buscar un Python que sirva -------------------------------
REM 3.11 es el minimo real: el programa usa datetime.UTC, que no existe
REM antes. Con 3.10 arrancaria y moriria con ImportError a mitad de
REM camino, que para el usuario es una ventana que se cierra sola.
set "PY="
if defined MVCLIENTE_PYTHON call :probar "%MVCLIENTE_PYTHON%"
call :probar "py -3.13"
call :probar "py -3.12"
call :probar "py -3.11"
call :probar "py -3"
call :probar "python"
call :probar "python3"
call :probar "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
call :probar "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
call :probar "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
call :probar "%ProgramFiles%\Python313\python.exe"
call :probar "%ProgramFiles%\Python312\python.exe"
call :probar "%ProgramFiles%\Python311\python.exe"
if not defined PY goto :sin_python

for /f "delims=" %%v in ('%PY% -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "VER=%%v"
echo   Python %VER% encontrado.

REM --- 2. Dependencias en una carpeta, sin venv ---------------------
set "PYTHONPATH=%LIBS%;%CD%"
%PY% -c "import fastapi, uvicorn, pydantic, openpyxl" >nul 2>&1
if not errorlevel 1 goto :correr

echo   Preparando el programa por primera vez (un minuto)...
if not exist "%DATOS%" mkdir "%DATOS%" >nul 2>&1
if not exist "%LIBS%" mkdir "%LIBS%" >nul 2>&1

REM Primero sin internet, desde las ruedas que vienen en el ZIP: es lo
REM que hace que esto ande en una maquina sin salida a PyPI.
if not exist "vendor" goto :con_internet
echo   - instalando desde vendor\ (sin internet)
%PY% -m pip install --no-index --find-links "vendor" --target "%LIBS%" --upgrade --no-warn-script-location -r requirements.txt >"%REGISTRO%" 2>&1
%PY% -c "import fastapi, uvicorn, pydantic, openpyxl" >nul 2>&1
if not errorlevel 1 goto :correr
echo   - vendor\ no alcanzo, probando con internet

:con_internet
echo   - instalando desde internet
%PY% -m pip install --target "%LIBS%" --upgrade --no-warn-script-location -r requirements.txt >>"%REGISTRO%" 2>&1
%PY% -c "import fastapi, uvicorn, pydantic, openpyxl" >nul 2>&1
if errorlevel 1 goto :sin_dependencias

:correr
echo   Listo. Abriendo el programa en tu navegador...
echo.
%PY% "packaging\lanzador_escritorio.py" %*
set "SALIDA=%ERRORLEVEL%"
if not "%SALIDA%"=="0" echo.& echo   El programa termino con error %SALIDA%.& call :pausa
exit /b %SALIDA%

:pausa
REM MVCLIENTE_SIN_PAUSA la define el CI: sin esto, un error dejaria el
REM "Presione una tecla para continuar" esperando para siempre y el
REM verificador de Windows se colgaria en vez de fallar.
if defined MVCLIENTE_SIN_PAUSA goto :eof
pause
goto :eof

REM ------------------------------------------------------------------
:sin_python
echo   No encontre Python 3.11 o mas nuevo en esta maquina.
echo.
echo   Instalalo de alguna de estas dos formas:
echo     - Microsoft Store, buscando "Python 3.12".
echo       Esa no pide permisos de administrador.
echo     - https://www.python.org/downloads/
echo       tildando "Add python.exe to PATH".
echo.
echo   Despues volve a abrir este archivo.
echo.
call :pausa
exit /b 1

:sin_dependencias
echo.
echo   No pude instalar las dependencias.
echo   El detalle quedo en:
echo     %REGISTRO%
echo.
echo   Suele ser una de estas dos:
echo     - la maquina no llega a PyPI (proxy o sin internet).
echo       Pedi el ZIP que trae la carpeta vendor\ adentro.
echo     - el antivirus corto la escritura en:
echo       %LIBS%
echo.
call :pausa
exit /b 1

:probar
REM Toma el primer interprete que exista Y sea 3.11+.
REM Una ruta con espacios ("C:\Program Files\...") hay que citarla, pero
REM "py -3.12" son dos palabras y citarlo lo rompe: por eso se cita solo
REM cuando el candidato termina en .exe.
if defined PY goto :eof
set "CAND=%~1"
if not defined CAND goto :eof
if /i "%CAND:~-4%"==".exe" (set CMD="%CAND%") else (set "CMD=%CAND%")
%CMD% -c "import sys;sys.exit(0 if sys.version_info[:2]>=(3,11) else 1)" >nul 2>&1
if errorlevel 1 goto :eof
set "PY=%CMD%"
goto :eof
