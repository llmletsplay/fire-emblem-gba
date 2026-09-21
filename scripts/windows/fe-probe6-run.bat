@echo off
REM Run fe_move_probe6 against local mGBA lua socket (default 8888).
setlocal
cd /d "%~dp0..\.."
if not defined FE_MGBA_PORT set FE_MGBA_PORT=8888
if exist "venv\Scripts\python.exe" (
  set PY=venv\Scripts\python.exe
) else (
  set PY=python
)
echo [fe-probe6-run] repo=%CD% port=%FE_MGBA_PORT%
"%PY%" tools\fe_move_probe6.py --port %FE_MGBA_PORT% %*
echo [fe-probe6-run] exit=%ERRORLEVEL%
endlocal
