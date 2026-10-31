@echo off
setlocal
title FastAPI Backend Server
cd /d "%~dp0"
set "PYTHONPATH=%CD%"
set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
echo ========================================================
echo Starting FastAPI Backend Server on http://127.0.0.1:8000 ...
echo ========================================================

if exist "%PYTHON_EXE%" goto verify_venv

echo Creating a Python 3.12+ virtual environment...
where py >nul 2>&1
if errorlevel 1 goto try_python_command

rem Use the newest installed Python 3 runtime, then check that it is 3.12 or newer.
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)" >nul 2>&1
if errorlevel 1 goto try_python_command
py -3 -m venv .venv
if errorlevel 1 goto setup_failed
goto verify_venv

:try_python_command
where python >nul 2>&1
if errorlevel 1 goto python_missing
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)" >nul 2>&1
if errorlevel 1 goto python_missing
python -m venv .venv
if errorlevel 1 goto setup_failed
goto verify_venv

:verify_venv
if not exist "%PYTHON_EXE%" goto setup_failed
"%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)" >nul 2>&1
if errorlevel 1 goto unsupported_venv
"%PYTHON_EXE%" -c "import fastapi, uvicorn, sqlalchemy, aiosqlite, celery, redis, jose, multipart, pydantic_settings, email_validator, aiofiles, slugify, pytesseract, cv2, PIL, pypdfium2, numpy, spacy" >nul 2>&1
if errorlevel 1 goto install_dependencies
goto start_server

:install_dependencies
if not exist "%PYTHON_EXE%" goto setup_failed
echo Installing backend dependencies. This may take several minutes on first run...
"%PYTHON_EXE%" -m ensurepip --upgrade >nul 2>&1
if errorlevel 1 goto setup_failed
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 goto setup_failed
"%PYTHON_EXE%" -m pip install -r requirements.txt
if errorlevel 1 goto setup_failed

goto start_server

:start_server
echo Starting backend. Wait for the healthy status before using the frontend.
"%PYTHON_EXE%" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
if errorlevel 1 echo Backend stopped with an error. Check the message above and backend/.env configuration.
goto end

:python_missing
echo ERROR: No installed Python 3.12+ runtime was found.
echo Install Python 3.12 or newer, enable the Python launcher or add python.exe to PATH, then rerun this file.
echo With the Windows Python Install Manager, you can install it using: py install 3.12
goto end

:unsupported_venv
echo ERROR: The existing .venv is not using Python 3.12 or newer.
echo Rename or remove only the project .venv folder, install Python 3.12+, then rerun this file.
goto end

:setup_failed
echo ERROR: Virtual environment or backend dependency setup failed.
echo Confirm Python 3.12+ is installed and that your internet connection is available, then retry.

:end
pause
endlocal
