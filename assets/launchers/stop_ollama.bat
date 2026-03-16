@echo off
taskkill /IM ollama.exe /F >nul 2>&1
echo Ollama stopped.
pause
