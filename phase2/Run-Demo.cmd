@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo First follow the Phase 2 setup steps in the repository README.
 pause
 exit /b 1
)
set "PATH=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin;%PATH%"
set "AR_DATA_DIR=%~dp0data"
set "AR_MODEL_CACHE=%~dp0data\models"
echo Open http://127.0.0.1:8765 and keep this window open.
".venv\Scripts\python.exe" -m uvicorn ar_companion.app:app --host 127.0.0.1 --port 8765
pause
