@echo off
REM ITORO Master Agent Dashboard Launcher
REM This script properly launches the Master Agent dashboard using Streamlit

echo 👑 Starting ITORO Master Agent Dashboard...
echo.
echo 📊 Dashboard will be available at: http://localhost:8501
echo 🔄 Close this window to stop the dashboard
echo.

cd /d "%~dp0"

REM Start Streamlit with auto browser launch
REM --server.headless false allows Streamlit to open browser automatically
python -m streamlit run src/dashboard_master.py --server.port 8501 --server.address localhost

pause
