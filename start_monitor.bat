@echo off
:: start_monitor.bat - Auto-start script for Game License Monitor Bot
:: This runs monitor.py in the background, restarting if it crashes.

cd /d "e:\ProjectAI\Project_alert_gov"

:loop
echo [%date% %time%] Starting Monitor Bot...
".venv\Scripts\python.exe" monitor.py
echo [%date% %time%] Monitor stopped. Restarting in 10 seconds...
timeout /t 10 /nobreak >nul
goto loop
