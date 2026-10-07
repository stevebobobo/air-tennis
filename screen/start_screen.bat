@echo off
rem Air Tennis big screen: start the server, then open the page in the browser.
cd /d "%~dp0"
start "" http://localhost:8000
py tennis_screen.py
pause
