@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Connector Vision SOP Agent v4.4.0 [Offline]

set OLLAMA_MODELS=%~dp0ollama_models
set OLLAMA_HOST=127.0.0.1:11434
set OLLAMA_ORIGINS=*
if not defined OLLAMA_CONTEXT_LENGTH set OLLAMA_CONTEXT_LENGTH=8192
if "%OLLAMA_CONTEXT_LENGTH%"=="0" set OLLAMA_CONTEXT_LENGTH=8192

rem Clear proxy variables so Ollama and the GUI talk to localhost directly.
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=
set ALL_PROXY=
set all_proxy=

rem Bypass corporate HTTP proxy for localhost (Ollama) connections.
rem Without this, Python requests routes http://127.0.0.1:11434 through the
rem company proxy (e.g. 107.100.72.56) which cannot reach this machine's
rem loopback adapter and returns 503 Service Unavailable.
set NO_PROXY=localhost,127.0.0.1,::1
set no_proxy=localhost,127.0.0.1,::1

echo ================================================================
echo  Connector Vision SOP Agent v4.4.0  [Fully Offline]
echo  GUI  : PyQt6 7-tab MainWindow (Vision, LLM Chat, SOP Editor, Training...)
echo  LLM  : IBM Granite Vision 3.2-2b  (Ollama, multimodal)
echo  YOLO : yolo26x embedded in EXE
echo ================================================================
echo.
echo [1/3] Starting Ollama server...
start /B "" "%~dp0ollama.exe" serve
timeout /t 30 /nobreak >nul
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
