@echo off
:: ============================================================
:: Connector Vision SOP Agent — First-Time Setup
:: Run this ONCE as Administrator after copying all files.
:: ============================================================
title First-Time Setup — Connector Vision SOP Agent

:: --- Must run as Administrator ---
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
set "MODEL_NAME=pedrolucas/smollm3:3b-q4_k_m"

echo ============================================================
echo  Connector Vision SOP Agent  ^|  First-Time Setup
echo ============================================================
echo.
echo This setup will:
echo   1. Register Ollama model directory
echo   2. Load SmolLM3-3B Q4_K_M LLM model from local files
echo   3. Verify the installation
echo.
echo This may take 2-5 minutes. Please wait...
echo.

:: --- Step 1: Verify Ollama EXE ---
if not exist "%OLLAMA_EXE%" (
    echo [ERROR] ollama.exe not found in: %BASE_DIR%
    echo         Please re-download the full installation package.
    pause
    exit /b 1
)
echo [OK] ollama.exe found.

:: --- Step 2: Set Ollama model directory ---
echo [INFO] Setting OLLAMA_MODELS environment variable...
setx OLLAMA_MODELS "%OLLAMA_MODELS%" /M >nul 2>&1
set "OLLAMA_MODELS=%OLLAMA_MODELS%"
echo [OK] Model directory set: %OLLAMA_MODELS%

:: --- Step 3: Verify model blobs exist ---
if not exist "%OLLAMA_MODELS%\blobs" (
    echo [WARN] Model blobs folder not found: %OLLAMA_MODELS%\blobs
    echo        Please extract portable-part2-smollm3 into:
    echo        %OLLAMA_MODELS%\
    echo        Then run this setup again.
    pause
    exit /b 1
)
echo [OK] Model blobs found.

:: --- Step 4: Start Ollama server temporarily ---
echo [INFO] Starting Ollama server for model registration...
start "" /B "%OLLAMA_EXE%" serve
timeout /t 5 /nobreak >nul

:: --- Step 5: Pull/register model from local files ---
echo [INFO] Registering %MODEL_NAME% model...
"%OLLAMA_EXE%" pull %MODEL_NAME% >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARN] Model registration returned non-zero.
    echo        This may be normal if the model was already registered.
)

:: --- Step 6: Quick test ---
echo [INFO] Testing LLM response (brief test)...
"%OLLAMA_EXE%" run %MODEL_NAME% "Say OK in one word." >nul 2>&1
if %errorLevel% equ 0 (
    echo [OK] LLM test passed.
) else (
    echo [WARN] LLM test did not respond. Check logs if LLM features fail.
)

:: --- Step 7: Stop temp Ollama server (start_agent.bat will start it properly) ---
taskkill /f /im ollama.exe >nul 2>&1

echo.
echo ============================================================
echo  Setup Complete!
echo ============================================================
echo.
echo  Next step:
echo    Double-click  start_agent.bat  to launch the agent.
echo.
echo  If any step showed [WARN], refer to README_INSTALL_EN.md
echo  Section 7 (Troubleshooting) for help.
echo.
pause
endlocal
exit /b 0
