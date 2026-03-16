@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Connector Vision SOP Agent v2.0 [Offline]

set OLLAMA_MODELS=%~dp0ollama_models
set OLLAMA_HOST=127.0.0.1:11434
set OLLAMA_ORIGINS=*

echo ================================================================
echo  Connector Vision SOP Agent v2.0.0  [Fully Offline]
echo  LLM  : phi4-mini-reasoning  (Microsoft, USA)
echo  YOLO : yolo26x embedded in EXE
echo ================================================================
echo.
echo [1/3] Starting Ollama server...
start /B "%~dp0ollama.exe" serve
timeout /t 15 /nobreak >nul

echo [2/3] Verifying LLM model...
"%~dp0ollama.exe" list
echo.

echo [3/3] Launching SOP Agent...
"%~dp0connector_vision_agent.exe"

echo.
echo Agent exited. Press any key to stop Ollama.
pause >nul
taskkill /IM ollama.exe /F >nul 2>&1
