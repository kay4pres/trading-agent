@echo off
REM Trader Agent launcher — starts the monitoring loop in a hidden window
REM Path to trader_agent.py
set SCRIPT=%~dp0trader_agent.py
set LOG=%~dp0logs\trader.log

REM Create logs dir if missing
if not exist "%~dp0logs" mkdir "%~dp0logs"

REM Launch Python in background (hidden window)
start /min "" pythonw "%SCRIPT%" >> "%LOG%" 2>&1
echo [%date% %time%] Trader started via launcher >> "%LOG%"
