@echo off
setlocal
cd /d "%~dp0"
title Launch Full Application Suite
echo ========================================================
echo Starting Workflow Automation & Document Intelligence Engine
echo ========================================================
echo [1/2] Launching backend on http://127.0.0.1:8000 ...
start "FastAPI Backend" run_backend.bat
echo Waiting for the backend health endpoint (up to 10 minutes for first-time setup)...
for /l %%i in (1,1,600) do (
    curl.exe -fsS http://127.0.0.1:8000/health >nul 2>&1
    if not errorlevel 1 goto backend_ready
    timeout /t 1 /nobreak >nul 2>&1
)
echo ERROR: Backend did not become healthy within 10 minutes.
echo Check the FastAPI Backend window for Python/dependency/database errors.
echo Frontend was not started because it cannot connect until the backend is ready.
goto end

:backend_ready
echo Backend health check passed.
echo [2/2] Launching Vite frontend on http://localhost:3000 ...
start "Vite QA Dashboard" run_frontend.bat
echo Frontend launched. Keep both server windows open.
echo Backend API docs: http://127.0.0.1:8000/docs

goto end

:end
pause
endlocal
