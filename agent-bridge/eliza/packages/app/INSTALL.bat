@echo off
echo ========================================
echo Eliza Desktop App Installer
echo ========================================
echo.
echo This will install the Eliza Desktop App.
echo.
echo Choose installer type:
echo 1. MSI Installer (Recommended)
echo 2. NSIS Installer
echo.
set /p choice="Enter choice (1 or 2): "

if "%choice%"=="1" (
    echo.
    echo Installing MSI...
    start "" "%~dp0src-tauri\target\release\bundle\msi\Eliza Desktop_1.6.4_x64_en-US.msi"
) else if "%choice%"=="2" (
    echo.
    echo Installing NSIS...
    start "" "%~dp0src-tauri\target\release\bundle\nsis\Eliza Desktop_1.6.4_x64-setup.exe"
) else (
    echo Invalid choice. Exiting.
    pause
    exit /b 1
)

echo.
echo Installer launched! Follow the on-screen instructions.
echo.
pause

