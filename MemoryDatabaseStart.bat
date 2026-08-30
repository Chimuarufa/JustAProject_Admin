@echo off
setlocal enabledelayedexpansion
title [adm.in] Memory Server // Sovereign Node
color 0B

echo ====================================================
echo   [adm.in] ENGINE INITIALIZATION SEQUENCE v1.5
echo   Target: itch.io Deployment Build
echo ====================================================
echo.

:: Set execution context strictly to the local directory
cd /d "%~dp0"

:: ------------------------------------------------------
:: PHASE 1: PYTHON VERIFICATION
:: ------------------------------------------------------
echo [SYSTEM]: Verifying Python runtime...
python --version >nul 2>&1
if %errorlevel% neq 0 (
echo.
echo ====================================================
echo [CRITICAL ERROR]: Python 3 is not detected!
echo ====================================================
echo To play [adm.in], your computer needs Python to run the AI memory.
echo.
echo 1. Go to: https://www.python.org/downloads/
echo 2. Download the latest installer.
echo 3. VERY IMPORTANT: When installing, check the box at the bottom
echo    that says "Add Python.exe to PATH".
echo 4. Restart your computer and try again.
echo.
pause
exit /b 1
)
echo [OK]: Python detected.

:: ------------------------------------------------------
:: PHASE 2: OLLAMA VERIFICATION
:: ------------------------------------------------------
echo.
echo [SYSTEM]: Verifying Ollama AI engine...
ollama --version >nul 2>&1
if %errorlevel% neq 0 (
echo.
echo ====================================================
echo [CRITICAL ERROR]: Ollama is not installed!
echo ====================================================
echo [adm.in] runs a localized AI directly on your GPU.
echo You need to install the Ollama engine first.
echo.
echo 1. Go to: https://ollama.com/download
echo 2. Download and install for Windows.
echo 3. Open Ollama from your Start Menu.
echo 4. Run this game again.
echo.
pause
exit /b 1
)

:: ------------------------------------------------------
:: PHASE 3: OLLAMA DAEMON CHECK
:: ------------------------------------------------------
echo [SYSTEM]: Checking if Ollama is running...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
echo.
echo ====================================================
echo [WARNING]: Ollama is installed, but not running!
echo ====================================================
echo Please open your Windows Start Menu, type "Ollama",
echo and click the app to start it. You should see a little
echo llama icon in your bottom-right system tray.
echo.
pause
exit /b 1
)
echo [OK]: Neural network socket open.

:: ------------------------------------------------------
:: PHASE 4: AUTO-MODEL DETECTION & DOWNLOAD
:: ------------------------------------------------------
echo.
echo [SYSTEM]: Scanning for required tensor weights (dolphin-mistral:7b)...
ollama list | findstr /I "dolphin-mistral:7b" >nul
if %errorlevel% neq 0 (
echo [SYSTEM]: Model missing. Initiating secure download...
echo [WARNING]: This is a 4.1GB download. It may take a few minutes.
echo.
ollama pull dolphin-mistral:7b
echo.
echo [OK]: Download complete. Tensor weights cached.
) else (
echo [OK]: Dolphin-Mistral 7B is already installed.
)

:: ------------------------------------------------------
:: PHASE 5: PYTHON SANDBOX (VENV)
:: ------------------------------------------------------
echo.
echo [SYSTEM]: Preparing isolated Python environment...
if not exist "venv" (
echo [SYSTEM]: First-time setup detected. Building virtual environment...
python -m venv venv
call venv\Scripts\activate

echo [SYSTEM]: Injecting neural dependencies... (This takes a moment)
if exist "requirements.txt" (
    python -m pip install --upgrade pip >nul 2>&1
    pip install -r requirements.txt
) else (
    echo [ERROR]: requirements.txt is missing from the folder!
)


) else (
call venv\Scripts\activate
)
echo [OK]: Environment active.

:: ------------------------------------------------------
:: PHASE 6: DATABASE VERIFICATION
:: ------------------------------------------------------
if not exist "adm_in_memory" (
echo [SYSTEM]: Generating clean persistence storage structure...
mkdir "adm_in_memory"
)

:: ------------------------------------------------------
:: PHASE 7: SERVER IGNITION
:: ------------------------------------------------------
echo.
echo ====================================================
echo [adm.in] BACKEND ONLINE. LEAVE THIS WINDOW OPEN.
echo ====================================================
echo [Cubie]: If you see me in this terminal, that means I'm awake!
echo [SYSTEM]: Booting memory_server.py...
echo.

:: Set environment variable to keep model in VRAM (Prevents 90s freeze)
set OLLAMA_KEEP_ALIVE=-1
python memory_server.py

echo.
echo [!] SERVER HALTED OR CRASHED.
pause