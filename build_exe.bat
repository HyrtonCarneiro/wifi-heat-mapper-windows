@echo off
setlocal
echo ============================================
echo   Wi-Fi Heat Mapper - Build Executavel Unico
echo ============================================
echo.

cd /d "%~dp0"

:: Verifica se o ambiente virtual existe e se o Python nele funciona
if not exist "venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado. Criando novo...
    python -m venv venv
)

venv\Scripts\python.exe --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Detectada mudanca de computador/caminho do Python.
    echo Reparando ambiente virtual...
    python -m venv --upgrade venv
)

:: Garante que o pyinstaller e dependencias estao instalados
if not exist "venv\Scripts\pyinstaller.exe" (
    echo Instalando PyInstaller e dependencias...
    venv\Scripts\python.exe -m pip install pyinstaller
    venv\Scripts\python.exe -m pip install -e .
)

:: Remove builds antigos para evitar conflitos
if exist "dist" rd /s /q "dist"
if exist "build" rd /s /q "build"
if exist "WiFi-Heat-Mapper.exe" del /f /q "WiFi-Heat-Mapper.exe"
if exist "%TEMP%\pyinstaller_whm" rd /s /q "%TEMP%\pyinstaller_whm"

set START_TIME=%TIME%
echo Build iniciado em: %START_TIME%
echo.

venv\Scripts\pyinstaller.exe --noconfirm --windowed --onefile --clean ^
 --workpath "%TEMP%\pyinstaller_whm" ^
 --distpath "dist" ^
 --name "WiFi-Heat-Mapper" ^
 --add-data "wifi_heat_mapper;wifi_heat_mapper" ^
 --hidden-import=wifi_heat_mapper ^
 --hidden-import=wifi_heat_mapper.misc ^
 --hidden-import=wifi_heat_mapper.config ^
 --hidden-import=wifi_heat_mapper.gui ^
 --hidden-import=wifi_heat_mapper.graph ^
 --hidden-import=wifi_heat_mapper.windows_wlan ^
 --hidden-import=wifi_heat_mapper.debugger ^
 --hidden-import=PIL ^
 --hidden-import=scipy.interpolate ^
 --hidden-import=matplotlib ^
 --hidden-import=numpy ^
 --hidden-import=FreeSimpleGUI ^
 --hidden-import=psutil ^
 --hidden-import=tqdm ^
 --hidden-import=openpyxl ^
 --collect-all matplotlib ^
 --collect-all scipy ^
 whm_app.py

echo.
if %ERRORLEVEL% EQU 0 (
    echo Movendo executavel para a pasta raiz...
    move /y "dist\WiFi-Heat-Mapper.exe" "."
    
    echo.
    echo ============================================
    echo   BUILD CONCLUIDO COM SUCESSO!
    echo   Inicio: %START_TIME%
    echo   Fim:    %TIME%
    echo   O programa agora esta na raiz: WiFi-Heat-Mapper.exe
    echo ============================================
) else (
    echo.
    echo ============================================
    echo   ERRO NO BUILD! Verifique os logs acima.
    echo ============================================
)
