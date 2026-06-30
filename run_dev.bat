@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
title Wi-Fi Heat Mapper - Modo Desenvolvimento

:: Usa o caminho onde o .bat esta guardado
set "BASE_DIR=%~dp0"
cd /d "%BASE_DIR%"

echo ====================================================
echo   Wi-Fi Heat Mapper - Diagnostic Mode
echo ====================================================
echo Pasta atual: %CD%
echo.

:: Verifica se o ambiente virtual existe e se o Python nele funciona
set "NEED_VENV=0"
if not exist "venv\Scripts\python.exe" (
    set "NEED_VENV=1"
) else (
    "venv\Scripts\python.exe" --version >nul 2>&1
    if !ERRORLEVEL! neq 0 (
        echo [INFO] Ambiente virtual corrompido ou caminho do Python alterado.
        echo [INFO] Recriando o ambiente virtual...
        rd /s /q venv
        set "NEED_VENV=1"
    )
)

if "!NEED_VENV!"=="1" (
    echo [INFO] Iniciando criacao do ambiente virtual...
    
    :: Tenta achar o Python
    set "PYTHON_CMD="
    python --version >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        set "PYTHON_CMD=python"
    ) else (
        py --version >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            set "PYTHON_CMD=py"
        )
    )

    if "!PYTHON_CMD!"=="" (
        echo [ERRO] Python nao encontrado no sistema.
        echo Instale o Python ^(certifique-se de marcar "Add to PATH"^) e tente novamente.
        pause
        exit /b
    )

    echo [INFO] Usando: !PYTHON_CMD!
    
    echo [INFO] Criando novo ambiente virtual ^(Aguarde o processo finalizar^)...
    !PYTHON_CMD! -m venv venv
    if !ERRORLEVEL! neq 0 (
        echo [ERRO] Falha ao criar ambiente virtual.
        pause
        exit /b
    )

    echo [INFO] Instalando dependencias do projeto...
    "venv\Scripts\python.exe" -m pip install --upgrade pip
    "venv\Scripts\python.exe" -m pip install -e .
    if !ERRORLEVEL! neq 0 (
        echo [ERRO] Falha ao instalar dependencias.
        pause
        exit /b
    )
    echo [INFO] Ambiente configurado com sucesso!
    echo.
)

echo [INFO] Iniciando Aplicacao...
echo.

:: Executa o programa
"venv\Scripts\python.exe" whm_app.py

if !ERRORLEVEL! neq 0 (
    echo.
    echo [ALERTA] O programa parou com erro !ERRORLEVEL!
    pause
) else (
    echo.
    echo [INFO] Programa encerrado normalmente.
    pause
)
