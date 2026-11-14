@echo off
setlocal
cd /d "%~dp0"

echo [1/4] Instalando PyInstaller y Pillow...
py -m pip install --upgrade pyinstaller pillow || goto :error

echo [2/4] Creando Widget Hora.exe...
py -m PyInstaller --onefile --noconsole --clean --name "Widget Hora" --icon icon.ico widget.py || goto :error

echo [3/4] Creando Widget Hora Config.exe...
py -m PyInstaller --onefile --noconsole --name "Widget Hora Config" --icon icon_config.ico config_app.py || goto :error

echo [4/4] Creando el instalador...
set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
  echo.
  echo No se encontro Inno Setup 6. Instalalo desde https://jrsoftware.org/isdl.php
  echo y vuelve a ejecutar este archivo.
  goto :error
)

"%ISCC%" installer.iss || goto :error

echo.
echo LISTO. Tu instalador esta en: installer\Widget_Hora_Setup.exe
pause
exit /b 0

:error
echo.
echo Hubo un error. Revisa los mensajes anteriores.
pause
exit /b 1
