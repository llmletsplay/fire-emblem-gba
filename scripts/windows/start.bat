@echo off
setlocal enabledelayedexpansion

REM Fire Emblem AI Agent - Unified Startup Script for Windows
REM This script starts both the backend and frontend in a clean, production-ready way

echo.
echo =========================
echo   Fire Emblem GBA AI Agent
echo =========================
echo.

set ROM_FILE=
set FE_GAME=
if exist ".env" (
    for /f "tokens=1,2 delims==" %%a in ('findstr /b "ROM_FILE= FE_GAME= LLM_PROVIDER=" .env') do (
        if "%%a"=="ROM_FILE" set ROM_FILE=%%b
        if "%%a"=="FE_GAME" set FE_GAME=%%b
        if "%%a"=="LLM_PROVIDER" set MODE=%%b
    )
)

if not defined ROM_FILE (
    set ROM_COUNT=0
    set DETECTED_ROM=
    for %%r in (FE7.gba fe7.gba FE8.gba fe8.gba) do (
        if exist "roms\%%r" (
            set /a ROM_COUNT+=1
            set DETECTED_ROM=%%r
        )
    )
    if "!ROM_COUNT!"=="1" (
        set ROM_FILE=!DETECTED_ROM!
    ) else (
        echo Error: ROM_FILE is not configured.
        echo Set ROM_FILE in .env to FE7.gba or FE8.gba.
        echo Examples: ROM_FILE=FE7.gba FE_GAME=fe7 or ROM_FILE=FE8.gba FE_GAME=fe8
        exit /b 1
    )
)

if defined MODE (
    set VALID_MODE=
    for %%m in (OPENAI ANTHROPIC GEMINI GROQ TOGETHER GROK OLLAMA LMSTUDIO CUSTOM ZAI MINIMAX) do (
        if /I "!MODE!"=="%%m" set VALID_MODE=1
    )
    if not defined VALID_MODE (
        echo Ignoring unsupported LLM_PROVIDER from .env: !MODE!
        set MODE=
    )
)

REM Check for required files
if not exist "roms\%ROM_FILE%" (
    echo Error: ROM file not found at roms\%ROM_FILE%
    echo Place your legally obtained FE7 or FE8 ROM in roms\ and set ROM_FILE in .env.
    echo Examples: ROM_FILE=FE7.gba FE_GAME=fe7 or ROM_FILE=FE8.gba FE_GAME=fe8
    exit /b 1
)

REM Check for Python
where python >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    exit /b 1
)

REM Check for Node.js
where node >nul 2>&1
if errorlevel 1 (
    echo Error: Node.js is not installed or not in PATH
    exit /b 1
)

REM Create necessary directories
echo Creating necessary directories...
if not exist "fe-client\public\chronicle\screenshots" mkdir "fe-client\public\chronicle\screenshots"
if not exist "assets\maps" mkdir "assets\maps"
if not exist "assets\sprites" mkdir "assets\sprites"
if not exist "screenshots" mkdir "screenshots"

REM Install Python dependencies if needed
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing/updating Python dependencies...
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install Python dependencies
    exit /b 1
)

REM Install Node dependencies
echo Installing frontend dependencies...
cd fe-client
if not exist "node_modules" (
    call npm install --quiet
    if errorlevel 1 (
        echo Failed to install Node dependencies
        exit /b 1
    )
)
cd ..

REM Start the React frontend
echo Starting React frontend...
cd fe-client
start /b cmd /c "npm run dev"
cd ..

REM Wait for frontend to start
timeout /t 3 /nobreak >nul

REM Run interactive setup to select/configure LLM provider
REM Only run interactive setup if LLM_PROVIDER is not set
if not defined MODE (
    REM This handles provider selection and API key entry
    echo Configuring LLM provider...

    REM Remove old result file
    del .llm_provider_result 2>nul

    REM Run interactively (user can see prompts and interact)
    python src\llm\interactive_setup.py
    if errorlevel 1 (
        echo LLM provider setup failed or was cancelled.
        exit /b 1
    )

    REM Read provider from result file
    if exist ".llm_provider_result" (
        set /p MODE=<.llm_provider_result
        del .llm_provider_result 2>nul
    )

    if not defined MODE (
        echo Error: No LLM provider configured.
        exit /b 1
    )
)

REM Export LLM_PROVIDER for Python to use
set LLM_PROVIDER=!MODE!
echo Using LLM provider: !MODE!
if defined FE_GAME (
    echo Using game: !FE_GAME! (!ROM_FILE!)
) else (
    echo Using ROM: !ROM_FILE! ^(game will be inferred^)
)

REM Start the Python backend with auto mode
echo Starting AI backend with !MODE! model...
start /b python src\core\run.py --auto

REM Display status
echo.
echo === All services started successfully! ===
echo.
echo Service URLs:
echo   * Frontend:  http://localhost:5173
echo   * WebSocket: ws://localhost:8765
echo   * mGBA:      localhost:8888
echo.
echo Instructions:
echo   1. Open http://localhost:5173 in your browser
echo   2. The AI will automatically start playing the configured Fire Emblem GBA ROM
echo   3. Switch to Chronicle tab to see story interpretations
echo   4. Press Ctrl+C to stop all services
echo.
echo Logs will appear below...
echo ======================================

REM Keep window open
pause >nul
