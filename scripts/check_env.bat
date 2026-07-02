@echo off
title Damai Env Check

echo ============================================
echo   Damai ATX Environment Check
echo ============================================
echo.

cd /d "%~dp0.."

echo [1/5] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Python not found. Please install Python 3.11+
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo [OK] %%i

echo [2/5] Checking adb...
adb version >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] adb not found. Please install Android Platform Tools
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('adb version') do echo [OK] %%i

echo [3/5] Checking device connection...
adb devices -l 2>nul | findstr /C:"device" | findstr /V "List" >nul
if %errorlevel% neq 0 (
    echo [WARN] No Android device detected
    echo        Connect phone and enable USB debugging
) else (
    for /f "tokens=*" %%i in ('adb devices -l ^| findstr device ^| findstr /V "List"') do echo [OK] %%i
)

echo [4/5] Checking Python packages...
python -c "import uiautomator2; print('uiautomator2: OK')" 2>nul || echo [FAIL] uiautomator2 not installed
python -c "import loguru; print('loguru: OK')" 2>nul || echo [FAIL] loguru not installed
python -c "import ntplib; print('ntplib: OK')" 2>nul || echo [FAIL] ntplib not installed
python -c "import airtest; print('airtest: OK')" 2>nul || echo [WARN] airtest not installed (image fallback unavailable)

echo [5/5] Checking config file...
if exist config.jsonc (
    echo [OK] config.jsonc found
) else (
    echo [WARN] config.jsonc not found (will use defaults)
)

echo.
echo ============================================
echo   Environment check complete!
echo ============================================
echo.

pause
