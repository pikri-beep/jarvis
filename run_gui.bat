@echo off
title JARVIS AI Assistant
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app\main.py
) else (
    python app\main.py
)
if errorlevel 1 pause
