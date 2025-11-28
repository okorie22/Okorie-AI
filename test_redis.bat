@echo off
echo 🧪 Testing Redis Installation and Connection
echo ============================================
echo.

REM Check if Redis is in PATH
echo 1. Checking Redis installation...
where redis-server >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Redis not found in PATH
    echo Checking common locations...

    if exist "C:\Redis\redis-server.exe" (
        echo ✅ Found Redis in C:\Redis
        goto :test_redis
    )

    if exist "C:\Program Files\Redis\redis-server.exe" (
        echo ✅ Found Redis in C:\Program Files\Redis
        goto :test_redis
    )

    echo ❌ Redis not found in common locations
    echo Please install Redis from: https://redis.io/download
    pause
    exit /b 1
)

echo ✅ Redis found in PATH

:test_redis
echo.
echo 2. Testing Redis functionality...

REM Test Redis server version
echo Testing Redis server...
redis-server --version
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Redis server test failed
    echo Redis may not be properly installed
    pause
    exit /b 1
)

echo.
echo 3. Testing Redis connection...

REM Start Redis temporarily for testing
echo Starting Redis for testing...
start /B redis-server >nul 2>&1
timeout /t 2 /nobreak > nul

REM Test connection
redis-cli ping >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ Redis connection successful
    echo 🔗 Redis is ready for agent communication

    REM Get some basic info
    echo.
    echo Redis Info:
    redis-cli info server | findstr "redis_version"
    redis-cli info server | findstr "tcp_port"
) else (
    echo ❌ Redis connection failed
    echo Redis server may not be running properly
)

echo.
echo 🎯 Redis test complete!

REM Kill the test Redis instance
taskkill /F /IM redis-server.exe >nul 2>&1

echo Press any key to continue...
pause >nul