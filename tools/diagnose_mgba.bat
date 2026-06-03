@echo off
echo.
echo ========================================
echo   mGBA Diagnostic Check
echo ========================================
echo.

echo Checking PATH for mGBA...
where mgba.exe 2>nul && (
    echo FOUND: mGBA is in PATH
    mgba.exe --version 2>nul
) || echo NOT IN PATH

echo.
echo Checking common locations...

if exist "C:\Program Files\mGBA\mgba.exe" (
    echo FOUND: C:\Program Files\mGBA\mgba.exe
    "C:\Program Files\mGBA\mgba.exe" --version 2>nul
)

if exist "C:\Program Files (x86)\mGBA\mgba.exe" (
    echo FOUND: C:\Program Files ^(x86^)\mGBA\mgba.exe
    "C:\Program Files (x86)\mGBA\mgba.exe" --version 2>nul
)

if exist "%USERPROFILE%\Downloads\mGBA\mgba.exe" (
    echo FOUND: %USERPROFILE%\Downloads\mGBA\mgba.exe
)

if exist "%USERPROFILE%\Desktop\mGBA\mgba.exe" (
    echo FOUND: %USERPROFILE%\Desktop\mGBA\mgba.exe
)

echo.
echo Searching for mgba.exe in user directories...
for /f "delims=" %%i in ('dir /s /b "%USERPROFILE%\mgba.exe" 2^>nul') do (
    echo FOUND: %%i
    set MGBA_PATH=%%i
    goto found
)

echo.
echo Searching in Downloads folder...
for /f "delims=" %%i in ('dir /s /b "%USERPROFILE%\Downloads\*mgba*.exe" 2^>nul') do (
    echo POSSIBLE: %%i
    set MGBA_PATH=%%i
)

:found
if defined MGBA_PATH (
    echo.
    echo Located mGBA at: %MGBA_PATH%
    echo.
    echo To use this, either:
    echo 1. Copy it to C:\Program Files\mGBA\
    echo 2. Add its directory to PATH
    echo 3. Copy mgba.exe to your project folder
) else (
    echo.
    echo mGBA not found on this system.
    echo Please download from: https://mgba.io/downloads.html
    echo.
    echo For Windows 64-bit, download:
    echo https://github.com/mgba-emu/mgba/releases/download/0.10.3/mGBA-0.10.3-win64.7z
    echo.
    echo Extract and place mgba.exe in:
    echo - C:\Program Files\mGBA\
    echo - Or your project folder
)

pause