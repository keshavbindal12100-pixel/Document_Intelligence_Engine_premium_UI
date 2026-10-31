@echo off
setlocal
title QA Frontend Test Client
cd /d "%~dp0frontend"
echo ========================================================
echo Starting Workflow Automation & Intelligence Dashboard
echo ========================================================
echo Frontend: http://localhost:3000
echo DocFlow UI: http://localhost:3000/app.html#/login
echo Main DocFlow homepage: http://localhost:3000/
echo Existing QA dashboard: http://localhost:3000/qa.html
echo Backend proxy target: http://127.0.0.1:8000

if not exist "package.json" goto frontend_folder_missing
if not exist "package-lock.json" goto lockfile_missing

where node >nul 2>&1
if errorlevel 1 goto node_missing
for /f "tokens=1 delims=." %%v in ('node -p "process.versions.node"') do set "NODE_MAJOR=%%v"
if not defined NODE_MAJOR goto node_missing
if %NODE_MAJOR% LSS 18 goto node_too_old

where npm >nul 2>&1
if errorlevel 1 goto npm_missing
for /f "tokens=1 delims=." %%v in ('npm --version') do set "NPM_MAJOR=%%v"
if not defined NPM_MAJOR goto npm_missing
if %NPM_MAJOR% LSS 9 goto npm_too_old

if not exist "node_modules\.bin\vite.cmd" (
    echo Installing locked frontend dependencies with npm ci...
    call npm ci --no-audit --no-fund
    if errorlevel 1 goto dependencies_failed
)
if not exist "node_modules\.bin\vite.cmd" goto vite_missing

echo Starting Vite dev server. Keep this window open while using the frontend...
call npm run dev
if errorlevel 1 echo Frontend stopped with an error. Check that port 3000 is free.
goto end

:frontend_folder_missing
echo ERROR: The frontend folder or package.json is missing.
echo Extract the complete project ZIP and run this file from the project root.
goto end

:lockfile_missing
echo ERROR: frontend/package-lock.json is missing. Extract the complete project ZIP again.
goto end

:node_missing
echo ERROR: Node.js is not installed or node.exe is not on PATH. Install the current Node.js LTS release, then reopen this window.
goto end

:node_too_old
echo ERROR: Node.js 18 or newer is required by Vite 5. Install the current Node.js LTS release.
goto end

:npm_missing
echo ERROR: npm was not found. Reinstall Node.js LTS with npm included, then reopen this window.
goto end

:npm_too_old
echo ERROR: npm 9 or newer is required for this project's lockfileVersion 3.
echo Update Node.js LTS, then reopen this window.
goto end

:dependencies_failed
echo ERROR: npm ci failed. Read the first npm error above and the debug-log path printed by npm.
echo Common causes include registry/network access, permissions, or a damaged npm cache; do not delete package-lock.json.
echo If the error remains, share the npm debug log referenced above.
goto end

:vite_missing
echo ERROR: Vite is still missing after npm ci. Check the npm output above and rerun this file.
goto end

:end
pause
endlocal
