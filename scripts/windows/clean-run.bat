@echo off
REM Clean Run Script - Deletes all runtime data for a fresh start
REM Usage: .\scripts\windows\clean-run.bat

echo === Fire Emblem AI Run Cleanup ===
echo This will delete all runtime data including saves, logs, and session history.
echo.

REM Confirm before proceeding
set /p confirm="Are you sure you want to continue? (y/N) "
if /i not "%confirm%"=="y" (
    echo Cleanup cancelled.
    exit /b 0
)

echo.
echo Cleaning up runtime data...
echo.

set DELETED_COUNT=0

echo 1. Cleaning generated knowledge and state files...
if exist "fe_knowledge.json" (
    del /q "fe_knowledge.json"
    echo   ^✓ Deleted: fe_knowledge.json
    set /a DELETED_COUNT+=1
)
if exist "state.json" (
    del /q "state.json"
    echo   ^✓ Deleted: state.json
    set /a DELETED_COUNT+=1
)
if exist ".llm_provider_result" (
    del /q ".llm_provider_result"
    echo   ^✓ Deleted: .llm_provider_result
    set /a DELETED_COUNT+=1
)
if exist "websocket.sock" (
    del /q "websocket.sock"
    echo   ^✓ Deleted: websocket.sock
    set /a DELETED_COUNT+=1
)
if exist "mgba.sock" (
    del /q "mgba.sock"
    echo   ^✓ Deleted: mgba.sock
    set /a DELETED_COUNT+=1
)

echo.
echo 2. Cleaning log files...
if exist "logs" (
    for /f %%A in ('dir /s /b logs\*.* 2^>nul ^| find /c /v ""') do set logcount=%%A
    rmdir /s /q logs 2>nul
    mkdir logs 2>nul
    echo   ^✓ Cleared: logs ^(%logcount% files^)
    set /a DELETED_COUNT+=1
)

echo.
echo 3. Cleaning session and chronicle data...
if exist "fe-client\public\chronicle" (
    rmdir /s /q "fe-client\public\chronicle" 2>nul
    echo   ^✓ Deleted: fe-client/public/chronicle
    set /a DELETED_COUNT+=1
)
if exist "assets\chronicle" (
    rmdir /s /q "assets\chronicle" 2>nul
    echo   ^✓ Deleted: assets/chronicle
    set /a DELETED_COUNT+=1
)

echo.
echo 4. Cleaning screenshot files...
if exist "screenshots" (
    rmdir /s /q screenshots 2>nul
    mkdir screenshots 2>nul
    echo   ^✓ Cleared: screenshots
    set /a DELETED_COUNT+=1
)
if exist "latest.png" (
    del /q "latest.png"
    echo   ^✓ Deleted: latest.png
    set /a DELETED_COUNT+=1
)
if exist "minimap.png" (
    del /q "minimap.png"
    echo   ^✓ Deleted: minimap.png
    set /a DELETED_COUNT+=1
)
del /q screenshot_*.png 2>nul
if %errorlevel%==0 (
    echo   ^✓ Deleted: screenshot_*.png files
)

echo.
echo 5. Cleaning build artifacts...
if exist "fe-client\dist" (
    rmdir /s /q "fe-client\dist" 2>nul
    echo   ^✓ Deleted: fe-client/dist
    set /a DELETED_COUNT+=1
)
if exist "fe-web\dist" (
    rmdir /s /q "fe-web\dist" 2>nul
    echo   ^✓ Deleted: fe-web/dist
    set /a DELETED_COUNT+=1
)

echo.
echo 6. Cleaning checkpoint data...
if exist "checkpoints" (
    rmdir /s /q checkpoints 2>nul
    mkdir checkpoints 2>nul
    echo   ^✓ Cleared: checkpoints
    set /a DELETED_COUNT+=1
)

echo.
echo 7. Cleaning temporary files...
if exist "tmp" (
    for /f "delims=" %%i in ('dir /b /a:-d tmp\*.* 2^>nul') do del /q "tmp\%%i" 2>nul
    for /f "delims=" %%i in ('dir /b /ad tmp\*.* 2^>nul') do rmdir /s /q "tmp\%%i" 2>nul
    echo   ^✓ Cleaned: tmp/
)

echo.
echo 8. Cleaning Python cache...
for /r %%i in (__pycache__) do if exist "%%i" rmdir /s /q "%%i" 2>nul
del /s /q *.pyc 2>nul
del /s /q *.pyo 2>nul
echo   ^✓ Cleaned Python cache files

echo.
echo 9. Cleaning game saves and save states...
del /q roms\*.sav 2>nul
if %errorlevel%==0 (
    echo   ^✓ Deleted: roms/*.sav files
)
del /q roms\*.ss* 2>nul
if %errorlevel%==0 (
    echo   ^✓ Deleted: roms/*.ss* files
)

echo.
echo === Cleanup Complete ===
echo Deleted %DELETED_COUNT% items
echo.
echo Note: ROM files (.gba) were preserved.
echo To start fresh, run: start.bat
