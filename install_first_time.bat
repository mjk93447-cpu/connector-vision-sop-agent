@echo off
:: ============================================================
:: Connector Vision SOP Agent v7.0.0 — First-Time Setup
:: Run this ONCE as Administrator after copying all files.
:: ============================================================
title First-Time Setup — Connector Vision SOP Agent v7.0.0

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] This script must be run as Administrator.
    echo         Right-click install_first_time.bat ^> "Run as administrator"
    pause
    exit /b 1
)

setlocal

set "BASE_DIR=%~dp0"
set "BASE_DIR=%BASE_DIR:~0,-1%"
set "OLLAMA_EXE=%BASE_DIR%\ollama.exe"
set "OLLAMA_MODELS=%BASE_DIR%\ollama_models"
set "SOP_GEN_MODEL=qwen3:8b"
set "CHAT_MODEL=gemma4:9b"

echo ============================================================
echo  Connector Vision SOP Agent v7.0.0  ^|  First-Time Setup
echo ============================================================
echo.
echo Required offline models:
echo   - %SOP_GEN_MODEL%  (SOP Generate / atomize)
echo   - %CHAT_MODEL%  (LLM Chat / recovery)
echo.

if not exist "%OLLAMA_EXE%" (
    echo [ERROR] ollama.exe not found in: %BASE_DIR%
    echo         Re-download the full installation package.
    pause
    exit /b 1
)
echo [OK] ollama.exe found.

echo [INFO] Setting OLLAMA_MODELS environment variable...
setx OLLAMA_MODELS "%OLLAMA_MODELS%" /M >nul 2>&1
set "OLLAMA_MODELS=%OLLAMA_MODELS%"
echo [OK] Model directory: %OLLAMA_MODELS%

if not exist "%OLLAMA_MODELS%\blobs" (
    echo [ERROR] Model blobs folder not found: %OLLAMA_MODELS%\blobs
    echo         Extract the LLM bundle into %OLLAMA_MODELS%\
    pause
    exit /b 1
)
echo [OK] Model blobs found.

if not exist "%OLLAMA_MODELS%\manifests" (
    echo [ERROR] Model manifests folder not found: %OLLAMA_MODELS%\manifests
    pause
    exit /b 1
)
echo [OK] Model manifests found.

echo [INFO] Starting Ollama server for model registration...
start "" /B "%OLLAMA_EXE%" serve
timeout /t 8 /nobreak >nul

echo [INFO] Verifying %SOP_GEN_MODEL% ...
"%OLLAMA_EXE%" show "%SOP_GEN_MODEL%" >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARN] %SOP_GEN_MODEL% not registered. Attempting local pull/register...
    "%OLLAMA_EXE%" pull %SOP_GEN_MODEL%
)

echo [INFO] Verifying %CHAT_MODEL% ...
"%OLLAMA_EXE%" show "%CHAT_MODEL%" >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARN] %CHAT_MODEL% not registered. Attempting local pull/register...
    "%OLLAMA_EXE%" pull %CHAT_MODEL%
)

echo [INFO] Installed models:
"%OLLAMA_EXE%" list

taskkill /f /im ollama.exe >nul 2>&1

echo.
echo ============================================================
echo  Setup Complete!
echo ============================================================
echo  Next: double-click start_agent.bat
echo  Docs: README_INSTALL_EN.md / docs/V7_0_0_FOCUS.md
echo.
pause
endlocal
exit /b 0
