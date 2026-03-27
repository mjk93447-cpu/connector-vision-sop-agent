@echo off
:: ============================================================
:: Connector Vision SOP Agent — Quick Start Launcher
:: Double-click this file to start the agent.
:: ============================================================
title Connector Vision SOP Agent

setlocal

:: --- Resolve base directory (same folder as this .bat) ---
set "BASE_DIR=%~dp0"
set "BASE_DIR=%BASE_DIR:~0,-1%"

:: --- Paths ---
set "OLLAMA_EXE=%BASE_DIR%\ollama.exe"
set "AGENT_EXE=%BASE_DIR%\connector_agent.exe"
set "OLLAMA_MODELS=%BASE_DIR%\ollama_models"

echo ============================================================
echo  Connector Vision SOP Agent  ^|  LINE AUTOMATION SYSTEM
echo ============================================================
echo.

:: --- Check agent EXE exists ---
if not exist "%AGENT_EXE%" (
    echo [ERROR] connector_agent.exe not found in:
    echo         %BASE_DIR%
    echo.
    echo Please verify installation. See README_INSTALL_EN.md
    pause
    exit /b 1
)

:: --- Start Ollama if available (LLM backend) ---
if exist "%OLLAMA_EXE%" (
    echo [INFO] Starting Ollama LLM server...
    set "OLLAMA_MODELS=%OLLAMA_MODELS%"
    start "" /B "%OLLAMA_EXE%" serve
    :: Wait briefly for Ollama to initialise
    timeout /t 3 /nobreak >nul
    echo [INFO] Ollama server started (Granite Vision 3.3-2b ready).
) else (
    echo [WARN] ollama.exe not found — LLM features will be disabled.
    echo        Run install_first_time.bat to set up Ollama.
)

echo.
echo [INFO] Launching Connector Vision SOP Agent...
echo.

:: --- Launch agent (GUI mode by default) ---
start "" "%AGENT_EXE%"

endlocal
exit /b 0
