@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo First follow the Phase 3 setup steps in the repository README.
 pause
 exit /b 1
)
set "VISION_DATA=%~dp0data-dedica"
if not defined VISION_MODELS set "VISION_MODELS=%~dp0models"
echo Open http://127.0.0.1:8766 and keep this window open.
".venv\Scripts\python.exe" -m uvicorn vision.app:app --host 127.0.0.1 --port 8766
pause
