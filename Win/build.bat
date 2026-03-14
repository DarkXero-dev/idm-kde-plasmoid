@echo off
:: IDM Quota Monitor — portable .exe builder
:: Requirements: Python 3.8.x (last version supporting Windows 7)
::   pip install -r requirements.txt
::   pip install pyinstaller
:: Run this from the Win\ folder on Windows.

echo [1/4] Copying logo...
copy /Y "..\idm-quota-monitor\contents\images\logo.png" "logo.png"
if errorlevel 1 (
    echo WARNING: logo.png not found — place it manually in this folder
)

echo [2/4] Cleaning previous build...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist

echo [3/4] Running PyInstaller...
pyinstaller idm_monitor.spec --clean

echo [4/4] Done.
if exist "dist\IDMQuotaMonitor.exe" (
    echo.
    echo  Build successful: dist\IDMQuotaMonitor.exe
    echo  Copy dist\IDMQuotaMonitor.exe anywhere and run — no install needed.
) else (
    echo  Build FAILED. Check output above for errors.
)
pause
