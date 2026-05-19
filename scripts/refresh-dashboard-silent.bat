@echo off
REM ============================================================
REM  Master Dashboard - Silent Refresh (for Task Scheduler)
REM  v2 - 19-May-26 - SA - GITHUB SOP migration
REM
REM  CHANGE FROM v1:
REM    v1 pushed via the in-place master-dashboard\.git, no safety
REM    guards. That was the 07-May overwrite path.
REM    v2 invokes COWORK\scripts\push-dashboard.sh --target master,
REM    which fresh-clones, runs the three-layer D-GIT-13 defence,
REM    and only commits if the source is not stale vs origin/main.
REM
REM  Same Task Scheduler entry: this file's path is unchanged.
REM ============================================================

setlocal
cd /d "%~dp0"

REM Force UTF-8 so Python unicode prints don't crash under Task Scheduler
set PYTHONIOENCODING=utf-8

REM Locate bash.exe (Git for Windows install)
set "BASH_CMD="
if exist "C:\Program Files\Git\bin\bash.exe" set "BASH_CMD=C:\Program Files\Git\bin\bash.exe"
if not defined BASH_CMD if exist "C:\Program Files (x86)\Git\bin\bash.exe" set "BASH_CMD=C:\Program Files (x86)\Git\bin\bash.exe"
if not defined BASH_CMD if exist "C:\Users\richb\AppData\Local\Programs\Git\bin\bash.exe" set "BASH_CMD=C:\Users\richb\AppData\Local\Programs\Git\bin\bash.exe"

REM Set up log path
set LOGFILE=%~dp0\..\logs\refresh-%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%.log
set LOGFILE=%LOGFILE: =0%
if not exist "%~dp0\..\logs" mkdir "%~dp0\..\logs"

echo Master Dashboard Refresh v2 - %date% %time% > "%LOGFILE%"
echo. >> "%LOGFILE%"

if not defined BASH_CMD (
    echo ERROR: bash.exe not found. Install Git for Windows. >> "%LOGFILE%"
    exit /b 1
)
echo Using bash: %BASH_CMD% >> "%LOGFILE%"

REM Step 1: Fetch prices + compute filters
echo [1/4] Fetching prices + computing filters... >> "%LOGFILE%"
python generate_master_data.py --full-universe >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo FAILED: generate_master_data.py exit code %ERRORLEVEL% >> "%LOGFILE%"
    exit /b 1
)

REM Step 2: Generate chart data
echo [2/4] Generating chart data... >> "%LOGFILE%"
python generate_chart_data.py --live >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo FAILED: generate_chart_data.py exit code %ERRORLEVEL% >> "%LOGFILE%"
    exit /b 1
)

REM Step 3: Build index.html
echo [3/4] Building index.html... >> "%LOGFILE%"
python build_dashboard.py >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo FAILED: build_dashboard.py exit code %ERRORLEVEL% >> "%LOGFILE%"
    exit /b 1
)

REM Step 4: Push via the canonical github-push SOP (REPLACES old git add/commit/push)
echo [4/4] Pushing via SOP (scripts/push-dashboard.sh --target master)... >> "%LOGFILE%"
"%BASH_CMD%" /c/Users/richb/Documents/COWORK/scripts/push-dashboard.sh --target master --message "scheduled refresh" --yes >> "%LOGFILE%" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: SOP push failed with exit code %ERRORLEVEL%. >> "%LOGFILE%"
    echo See Layer 1/2/3 detail above. Common causes: stale source blocked by Layer 1 (re-run regen pipeline first); or transient network failure on clone. >> "%LOGFILE%"
    exit /b 1
)

echo Refresh complete. >> "%LOGFILE%"
exit /b 0
