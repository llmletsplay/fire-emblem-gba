@echo off
setlocal enabledelayedexpansion

echo.
echo =========================================
echo   Fire Emblem AI - Windows Setup Script
echo =========================================
echo.
echo This script will set up your development environment
echo for Windows with CUDA support (RTX 2060 Max-Q)
echo.

REM Check Python installation
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo Found Python %PYTHON_VERSION%

REM Create virtual environment
if not exist venv (
    echo.
    echo Creating Python virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully
) else (
    echo Virtual environment already exists
)

REM Activate virtual environment
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Check CUDA availability
echo.
echo Checking for CUDA support...
python -c "import platform; print(f'System: {platform.system()} {platform.machine()}')"

REM Install PyTorch with CUDA
echo.
echo Installing PyTorch with CUDA support...
echo This may take several minutes for the first installation...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
if errorlevel 1 (
    echo.
    echo WARNING: Failed to install PyTorch with CUDA
    echo Trying CPU-only version...
    pip install torch torchvision torchaudio
)

REM Verify PyTorch installation
echo.
echo Verifying PyTorch installation...
python -c "import torch; cuda='CUDA' if torch.cuda.is_available() else 'CPU'; print(f'PyTorch {torch.__version__} installed with {cuda} support')"
if errorlevel 1 (
    echo ERROR: PyTorch installation verification failed
    pause
    exit /b 1
)

REM Install core requirements first
echo.
echo Installing core Python dependencies...
pip install websockets python-dotenv aiofiles openai anthropic numpy
if errorlevel 1 (
    echo WARNING: Some core requirements failed to install
)

REM Install other requirements
echo.
echo Installing remaining Python dependencies...
pip install -r requirements.txt 2>nul
if errorlevel 1 (
    echo WARNING: Some additional requirements failed to install
    echo This is normal if some packages are not needed
)

REM Install RL-specific requirements
echo.
echo Installing RL-specific dependencies...
pip install opencv-python-headless gymnasium numpy matplotlib tqdm tensorboard
if errorlevel 1 (
    echo WARNING: Some RL requirements failed to install
)

REM Install Windows-specific packages
echo.
echo Installing Windows-specific packages...
pip install pywin32 psutil
if errorlevel 1 (
    echo WARNING: Some Windows packages failed to install
)

REM Check Node.js for frontend
echo.
echo Checking Node.js installation...
where node >nul 2>&1
if errorlevel 1 (
    echo WARNING: Node.js is not installed
    echo Frontend will not work without Node.js
    echo Download from: https://nodejs.org/
) else (
    for /f "tokens=1" %%i in ('node --version') do set NODE_VERSION=%%i
    echo Found Node.js !NODE_VERSION!

    REM Install frontend dependencies
    echo Installing frontend dependencies...
    cd fe-client
    if not exist node_modules (
        call npm install
    ) else (
        echo Frontend dependencies already installed
    )
    cd ..
)

REM Final verification
echo.
echo =========================================
echo   Setup Complete!
echo =========================================
echo.

REM Show installed packages
python -c "import cv2; print(f'OpenCV: {cv2.__version__}')" 2>nul || echo OpenCV: Not installed

echo.
echo You can now run:
echo   - start.bat              : Start the main application
echo.
pause