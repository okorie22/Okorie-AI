@echo off
echo ============================================
echo 🚀 ITORO Trading Environment Startup
echo ============================================
echo.

REM Check if Redis is installed (skip auto-install, just verify)
echo 🔍 Checking for Redis installation...
where redis-server >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️  Redis not found in PATH
    echo Checking common installation locations...
    echo.

    REM Check common Redis locations
    set "REDIS_FOUND="
    if exist "C:\Redis\redis-server.exe" (
        echo ✅ Found Redis in C:\Redis
        set "REDIS_FOUND=C:\Redis"
    ) else if exist "C:\Program Files\Redis\redis-server.exe" (
        echo ✅ Found Redis in C:\Program Files\Redis
        set "REDIS_FOUND=C:\Program Files\Redis"
    ) else (
        echo ❌ Redis not found in common locations
        echo Please ensure Redis is installed and in PATH
        echo You can still run Eliza without Redis (agents won't connect)
        echo.
        goto :skip_redis
    )

    REM Add found Redis to PATH
    if defined REDIS_FOUND (
        echo Adding Redis to PATH...
        setx PATH "%PATH%;%REDIS_FOUND%" /M >nul 2>&1
        set "PATH=%PATH%;%REDIS_FOUND%"
        echo ✅ Redis added to PATH
    )
)

echo ✅ Redis found in PATH
echo.

REM Start Redis in background
echo 🔄 Starting Redis server...
start "Redis Server" redis-server.exe
timeout /t 3 /nobreak > nul

goto :test_redis

:skip_redis
echo ⚠️  Skipping Redis startup (not required for basic Eliza functionality)
echo Trading agents won't be able to connect, but AI will still work
echo.
goto :start_eliza

:test_redis

REM Verify Redis is running
:test_redis
redis-cli ping >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo ✅ Redis is running and responding
    echo 🔗 Agent communication enabled
) else (
    echo ⚠️  Redis not responding (may still be starting)
    echo 🔗 Agent communication disabled
)
echo.

:start_eliza
REM Start Eliza server
echo 🚀 Starting Eliza ITORO server...
cd eliza
node start.js

REM Keep window open
pause
