@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Connector Vision SOP Agent v3.0 [Offline]

set OLLAMA_MODELS=%~dp0ollama_models
set OLLAMA_HOST=127.0.0.1:11434
set OLLAMA_ORIGINS=*

echo ================================================================
echo  Connector Vision SOP Agent v3.0.0  [Fully Offline]
echo  GUI  : PyQt6 6-tab MainWindow (Vision, LLM Chat, Audit...)
echo  LLM  : phi4-mini-reasoning  (Microsoft, USA)
echo  YOLO : yolo26x embedded in EXE
echo ================================================================
echo.
echo [1/3] Starting Ollama server...
start /B "" "%~dp0ollama.exe" serve
timeout /t 20 /nobreak >nul
echo Ollama startup wait complete.

echo [2/3] Verifying LLM model (OLLAMA_MODELS=%OLLAMA_MODELS%)...
"%~dp0ollama.exe" list
if errorlevel 1 (
    echo [WARN] ollama list returned an error. Ollama may still be starting.
    echo        If the EXE fails to connect, wait 10s and retry start_agent.bat.
)
echo.

echo [3/3] Launching SOP Agent (GUI mode)...
"%~dp0connector_vision_agent.exe"

echo.
echo Agent exited. Press any key to stop Ollama.
pause >nul
taskkill /IM ollama.exe /F >nul 2>&1
