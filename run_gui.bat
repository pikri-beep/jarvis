@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" run_gui.pyw
) else if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\python.exe" run_gui.pyw
) else (
    start "" pythonw run_gui.pyw
)
