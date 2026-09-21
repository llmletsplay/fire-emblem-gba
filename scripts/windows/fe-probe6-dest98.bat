@echo off
REM Probe confirm-A after pathing to tutorial dest (9,8). Optional: pass extra args.
setlocal
cd /d "%~dp0..\.."
if not defined FE_MGBA_PORT set FE_MGBA_PORT=8888
call scripts\windows\fe-probe6-run.bat --dest 9,8 --loadstate 0 %*
endlocal
