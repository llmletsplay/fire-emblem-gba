@echo off
setlocal enabledelayedexpansion

echo.
echo ======================================
echo   mGBA Installation for Windows
echo ======================================
echo.

REM Check if mGBA is already installed
where mgba.exe >nul 2>&1
if not errorlevel 1 (
    echo mGBA is already installed and in PATH!
    mgba.exe --version 2>nul || echo mGBA found in PATH
    pause
    exit /b 0
)

REM Check common install locations
set MGBA_PATHS[0]=C:\Program Files\mGBA\mgba.exe
set MGBA_PATHS[1]=C:\Program Files (x86)\mGBA\mgba.exe

for /l %%i in (0,1,1) do (
    if exist "!MGBA_PATHS[%%i]!" (
        echo mGBA found at: !MGBA_PATHS[%%i]!
        echo Adding to PATH for this session...
        for %%p in ("!MGBA_PATHS[%%i]!") do set "PATH=%%~dpp;!PATH!"
        pause
        exit /b 0
    )
)

echo mGBA not found. Let's install it!
echo.
echo This script will:
echo 1. Download mGBA 0.10.3 for Windows
echo 2. Extract it to Program Files\mGBA
echo 3. Add it to your PATH
echo.
set /p CONFIRM="Continue with installation? (y/n): "
if /i not "%CONFIRM%"=="y" exit /b 1

echo.
echo Downloading mGBA...
echo Please wait, this may take a few minutes...

REM Create temp directory
set TEMP_DIR=%TEMP%\mgba_install
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

REM Download mGBA using PowerShell
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/mgba-emu/mgba/releases/download/0.10.3/mGBA-0.10.3-win64.7z' -OutFile '%TEMP_DIR%\mGBA.7z'}"

if not exist "%TEMP_DIR%\mGBA.7z" (
    echo Failed to download mGBA
    echo Please download manually from: https://mgba.io/downloads.html
    pause
    exit /b 1
)

echo Downloaded successfully!
echo.
echo Extracting mGBA...

REM Extract using PowerShell (Windows 10+ has built-in support for some archives)
REM For 7z files, we'll try to use PowerShell with some workarounds
powershell -Command "& {Add-Type -AssemblyName System.IO.Compression.FileSystem; try { [System.IO.Compression.ZipFile]::ExtractToDirectory('%TEMP_DIR%\mGBA.7z', '%TEMP_DIR%\extracted') } catch { Write-Host 'Extraction failed. Please install 7-Zip or extract manually.'; exit 1 }}"

if errorlevel 1 (
    echo.
    echo Extraction failed. You have a few options:
    echo 1. Install 7-Zip from https://www.7-zip.org/
    echo 2. Download mGBA manually from https://mgba.io/downloads.html
    echo 3. Extract the downloaded file from %TEMP_DIR%\mGBA.7z manually
    echo.
    echo Then copy mgba.exe to one of these locations:
    echo   - C:\Program Files\mGBA\
    echo   - Your project directory
    pause
    exit /b 1
)

REM Find extracted mgba.exe
for /r "%TEMP_DIR%\extracted" %%f in (mgba.exe) do (
    set MGBA_EXE=%%f
    goto found_exe
)

:found_exe
if not defined MGBA_EXE (
    echo Could not find mgba.exe in extracted files
    echo Please check %TEMP_DIR%\extracted manually
    pause
    exit /b 1
)

echo Found mGBA executable: %MGBA_EXE%
echo.
echo Installing mGBA to C:\Program Files\mGBA...

REM Create program files directory (requires admin)
if not exist "C:\Program Files\mGBA" (
    mkdir "C:\Program Files\mGBA" 2>nul || (
        echo.
        echo ERROR: Cannot create directory in Program Files
        echo Please run this script as Administrator, or
        echo Copy mgba.exe manually to your project directory
        echo.
        echo Source: %MGBA_EXE%
        echo Destination: C:\Program Files\mGBA\mgba.exe
        pause
        exit /b 1
    )
)

REM Copy mGBA files
for /f %%f in ('dir /b "%TEMP_DIR%\extracted\*"') do (
    copy "%TEMP_DIR%\extracted\%%f" "C:\Program Files\mGBA\" >nul 2>&1
)

REM Verify installation
if exist "C:\Program Files\mGBA\mgba.exe" (
    echo.
    echo ✅ mGBA installed successfully!
    echo Location: C:\Program Files\mGBA\mgba.exe
    echo.
    echo Adding to system PATH...

    REM Add to PATH for current session
    set "PATH=C:\Program Files\mGBA;%PATH%"

    REM Try to add to system PATH permanently (may require admin)
    powershell -Command "& {[Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';C:\Program Files\mGBA', 'Machine')}" 2>nul || (
        echo Note: Could not add to system PATH permanently
        echo You may need to add C:\Program Files\mGBA to your PATH manually
    )

    echo.
    echo Testing mGBA installation...
    "C:\Program Files\mGBA\mgba.exe" --version 2>nul && echo ✅ mGBA is working! || echo ⚠️  mGBA may have issues

) else (
    echo ❌ Installation failed
    echo Please try manual installation from https://mgba.io/downloads.html
)

REM Cleanup
rmdir /s /q "%TEMP_DIR%" 2>nul

echo.
echo Installation complete!
echo You can now run the Fire Emblem RL training scripts.
pause