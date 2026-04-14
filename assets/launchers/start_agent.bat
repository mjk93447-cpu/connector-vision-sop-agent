@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Connector Vision SOP Agent v6.0.0 [Offline]

set MODEL_ROOT=%~dp0ollama_models
if exist "%~dp0llm_stage\ollama_split_manifest.json" set MODEL_ROOT=%~dp0llm_stage
if exist "%~dp0ollama_models\ollama_split_manifest.json" set MODEL_ROOT=%~dp0ollama_models
set OLLAMA_MODELS=%MODEL_ROOT%
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
echo  Connector Vision SOP Agent v6.0.0  [Fully Offline]
echo  GUI  : PyQt6 7-tab MainWindow (Vision, SOP Generate, SOP Editor, Training...)
echo  LLM  : Gemma 4 26B A4B IT Q4_K_M  (Ollama + TurboQuant)
echo  YOLO : GUI runtime + local pretrained fine-tune seed bundle
echo ================================================================
echo.
echo [prep] Ollama model root: %OLLAMA_MODELS%
if exist "%~dp0restore_ollama_stage.ps1" (
    if exist "%OLLAMA_MODELS%\ollama_split_manifest.json" (
        echo [prep] Restoring split Ollama blobs...
        powershell -ExecutionPolicy Bypass -File "%~dp0restore_ollama_stage.ps1" -ModelsRoot "%OLLAMA_MODELS%"
        if errorlevel 1 (
            echo [WARN] Failed to restore split Ollama blobs. LLM startup may fail.
        )
    )
)

echo [1/3] Starting Ollama server...
if exist "%~dp0ollama.exe" (
    start /B "" "%~dp0ollama.exe" serve
    timeout /t 30 /nobreak >nul
    echo Ollama startup wait complete.
) else (
    echo [WARN] ollama.exe not found. Continuing with GUI smoke / non-LLM mode.
)

echo [2/3] Verifying Gemma + TurboQuant runtime (OLLAMA_MODELS=%OLLAMA_MODELS%)...
if exist "%~dp0ollama.exe" (
    "%~dp0ollama.exe" list
    if errorlevel 1 (
        echo [WARN] ollama list returned an error. Ollama may still be starting.
        echo        If the EXE fails to connect, wait 10s and retry start_agent.bat.
    ) else (
        "%~dp0ollama.exe" show "gemma4:26b-a4b-it-q4_K_M" >nul 2>&1
        if errorlevel 1 (
            echo [WARN] Expected Gemma 4 TurboQuant model is not ready in %OLLAMA_MODELS%.
            echo        Extract the verified LLM bundle so llm_stage\ or ollama_models\ is present.
        ) else (
            echo Gemma 4 TurboQuant model is ready.
        )
    )
) else (
    echo [INFO] LLM verification skipped because ollama.exe is absent.
)
echo.

echo [3/3] Launching SOP Agent (GUI mode)...
"%~dp0connector_vision_agent.exe"

echo.
echo Agent exited. Press any key to stop Ollama.
pause >nul
if exist "%~dp0ollama.exe" taskkill /IM ollama.exe /F >nul 2>&1
