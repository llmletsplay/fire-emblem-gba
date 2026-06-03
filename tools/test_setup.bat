@echo off
setlocal enabledelayedexpansion

echo.
echo ===================================
echo   Fire Emblem AI - Setup Test
echo ===================================
echo.

REM Activate virtual environment
if exist venv (
    echo ✅ Virtual environment found
    call venv\Scripts\activate.bat
) else (
    echo ❌ Virtual environment not found
    echo Run setup_windows.bat first
    exit /b 1
)

REM Test Python dependencies
echo.
echo Testing Python dependencies...

python -c "import websockets; print('✅ websockets')" 2>nul || echo "❌ websockets missing"
python -c "import torch; print('✅ torch')" 2>nul || echo "❌ torch missing"
python -c "import cv2; print('✅ opencv')" 2>nul || echo "❌ opencv missing"
python -c "import numpy; print('✅ numpy')" 2>nul || echo "❌ numpy missing"

REM Test mGBA
echo.
echo Testing mGBA installation...
where mgba.exe >nul 2>&1 && (
    echo ✅ mGBA found in PATH
    mgba.exe --version 2>nul || echo "mGBA executable found"
) || (
    echo ❌ mGBA not found in PATH
    if exist "C:\Program Files\mGBA\mgba.exe" (
        echo ✅ mGBA found at C:\Program Files\mGBA\mgba.exe
    ) else if exist "C:\Program Files (x86)\mGBA\mgba.exe" (
        echo ✅ mGBA found at C:\Program Files (x86)\mGBA\mgba.exe
    ) else (
        echo ❌ mGBA not installed
        echo Run install_mgba_windows.bat to install it
    )
)

REM Test ROM file
echo.
echo Testing ROM file...
if exist "roms\FE7.gba" (
    echo ✅ ROM file found: roms\FE7.gba
) else if exist "roms\FE8.gba" (
    echo ✅ ROM file found: roms\FE8.gba
) else if exist "roms\fe7.gba" (
    echo ✅ ROM file found: roms\fe7.gba
) else if exist "roms\fe8.gba" (
    echo ✅ ROM file found: roms\fe8.gba
) else (
    echo ❌ ROM file not found
    echo Please place a legally obtained FE7 or FE8 ROM in the roms\ folder
    echo   Expected: roms\FE7.gba or roms\FE8.gba
)

REM Test Lua script
echo.
echo Testing Lua script...
if exist "socketserver.lua" (
    echo ✅ Lua script found: socketserver.lua
) else (
    echo ❌ Lua script missing: socketserver.lua
)

REM Test Node.js (for frontend)
echo.
echo Testing Node.js...
where node >nul 2>&1 && (
    for /f "tokens=1" %%i in ('node --version') do (
        echo ✅ Node.js found: %%i
    )
) || (
    echo ❌ Node.js not found
    echo Install from https://nodejs.org/
)

if exist "fe-client\node_modules" (
    echo ✅ Frontend dependencies installed
) else (
    echo ❌ Frontend dependencies not installed
    echo Run 'npm install' in the fe-client directory
)

echo.
echo ===================================
echo Test complete!
echo.
echo If all items show check marks, you can run:
echo   start.bat
echo.
echo If any items show X, please fix them first.
echo ===================================
pause
