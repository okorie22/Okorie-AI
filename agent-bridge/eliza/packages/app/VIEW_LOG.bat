@echo off
echo Opening Eliza Desktop log file...
echo.
if exist "%APPDATA%\Eliza Desktop\eliza-desktop.log" (
    notepad "%APPDATA%\Eliza Desktop\eliza-desktop.log"
) else (
    echo Log file not found at: %APPDATA%\Eliza Desktop\eliza-desktop.log
    echo The app may not have run yet, or there was an error creating the log file.
    pause
)

