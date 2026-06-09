@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Connector Vision SOP Agent v7.0.0 [Offline]

set MODEL_ROOT=%~dp0ollama_models
if exist "%~dp0llm_stage\ollama_split_manifest.json" set MODEL_ROOT=%~dp0llm_stage
if exist "%~dp0ollama_models\ollama_split_manifest.json" set MODEL_ROOT=%~dp0ollama_models
set OLLAMA_MODELS=%MODEL_ROOT%
set OLLAMA_HOST=127.0.0.1:11434
set OLLAMA_ORIGINS=*
if not defined OLLAMA_CONTEXT_LENGTH set OLLAMA_CONTEXT_LENGTH=32768
if "%OLLAMA_CONTEXT_LENGTH%"=="0" set OLLAMA_CONTEXT_LENGTH=32768

set SOP_GEN_MODEL=qwen3:8b
set CHAT_MODEL=gemma4:9b

rem Clear proxy variables so Ollama and the GUI talk to localhost directly.
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=
set ALL_PROXY=
set all_proxy=

rem Bypass corporate HTTP proxy for localhost (Ollama) connections.
set NO_PROXY=localhost,127.0.0.1,::1
set no_proxy=localhost,127.0.0.1,::1

echo ================================================================
echo  Connector Vision SOP Agent v7.0.0  [Fully Offline]
echo  GUI  : PyQt6 MainWindow (SOP Generate, SOP Editor, Training...)
echo  SOP  : %SOP_GEN_MODEL%  (document atomize / 4-pass LLM)
echo  Chat : %CHAT_MODEL%  (LLM Chat + recovery_action)
echo  YOLO : yolo26x_local_pretrained.pt runtime seed
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

echo [2/3] Verifying offline LLM models (OLLAMA_MODELS=%OLLAMA_MODELS%)...
if exist "%~dp0ollama.exe" (
    "%~dp0ollama.exe" list
    if errorlevel 1 (
        echo [WARN] ollama list returned an error. Ollama may still be starting.
    ) else (
        "%~dp0ollama.exe" show "%SOP_GEN_MODEL%" >nul 2>&1
        if errorlevel 1 (
            echo [WARN] SOP Generate model %SOP_GEN_MODEL% is not ready.
            echo        Stage qwen3:8b into %OLLAMA_MODELS% or run install_first_time.bat.
        ) else (
            echo SOP Generate model %SOP_GEN_MODEL% is ready.
        )
        "%~dp0ollama.exe" show "%CHAT_MODEL%" >nul 2>&1
        if errorlevel 1 (
            echo [WARN] Chat model %CHAT_MODEL% is not ready.
            echo        Stage gemma4:9b into %OLLAMA_MODELS% or run install_first_time.bat.
        ) else (
            echo Chat model %CHAT_MODEL% is ready.
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
