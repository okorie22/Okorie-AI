@echo off
REM Quick Start Script for Windows
REM Starts Redis and the IUL Appointment Setter System

echo ========================================
echo IUL Appointment Setter - Quick Start
echo ========================================
echo.

REM Check if Redis is in PATH
where redis-server >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] redis-server not found in PATH
    echo Please ensure Redis is installed and running
    echo.
    echo Download Redis for Windows from:
    echo https://github.com/microsoftarchive/redis/releases
    echo.
    pause
) else (
    echo Starting Redis server...
    start "Redis Server" redis-server
    timeout /t 3 /nobreak >nul
)

echo.
echo Starting IUL Appointment Setter System...
echo.

cd /d "%~dp0.."
python main.py

pause
