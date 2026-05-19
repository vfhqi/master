@echo off
REM ============================================================
REM  Master Dashboard - Full Refresh Pipeline (manual)
REM  v2 - 19-May-26 - SA - GITHUB SOP migration
REM
REM  Double-click to run, or run from terminal. Pauses at end.
REM  For unattended Task Scheduler runs, use refresh-dashboard-silent.bat.
REM
REM  CHANGE FROM v1:
REM    v1 pushed via the in-place master-dashboard\.git, no safety guards.
REM    v2 invokes COWORK\scripts\push-dashboard.sh --target master, which
REM    fresh-clones and runs the three-layer D-GIT-13 defence.
REM ============================================================

setlocal
cd /d "%~dp0"

REM Locate bash.exe (Git for Windows install)
set "BASH_CMD="
if exist "C:\Program Files\Git\bin\bash.exe" set "BASH_CMD=C:\Program Files\Git\bin\bash.exe"
if not defined BASH_CMD if exist "C:\Program Files (x86)\Git\bin\bash.exe" set "BASH_CMD=C:\Program Files (x86)\Git\bin\bash.exe"
if not defined BASH_CMD if exist "C:\Users\richb\AppData\Local\Programs\Git\bin\bash.exe" set "BASH_CMD=C:\Users\richb\AppData\Local\Programs\Git\bin\bash.exe"

echo.
echo ========================================
echo  Master Dashboard - Full Refresh v2
echo  %date% %time%
echo ========================================
echo.

if not defined BASH_CMD (
    echo ERROR: bash.exe not found. Install Git for Windows.
    pause
    exit /b 1
)

REM Step 1: Fetch prices + filters
echo [1/4] Fetching prices + computing filters...
python generate_master_data.py --full-universe
if %ERRORLEVEL% NEQ 0 goto :error

echo      Done.
echo.

REM Step 2: Generate chart data
echo [2/4] Generating chart data (per-ticker JS files)...
python generate_chart_data.py --live
if %ERRORLEVEL% NEQ 0 goto :error

echo      Done.
echo.

REM Step 3: Build HTML
echo [3/4] Building index.html...
python build_dashboard.py
if %ERRORLEVEL% NEQ 0 goto :error

echo      Done.
echo.

REM Step 4: Push via the canonical github-push SOP
echo [4/4] Pushing via SOP (scripts/push-dashboard.sh --target master)...
"%BASH_CMD%" /c/Users/richb/Documents/COWORK/scripts/push-dashboard.sh --target master --message "manual refresh" --yes
if %ERRORLEVEL% NEQ 0 goto :error

echo.
echo ========================================
echo  Refresh complete.
echo ========================================
echo.
pause
goto :eof

:error
echo.
echo ========================================
echo  PIPELINE FAILED - see error above.
echo ========================================
echo.
pause
exit /b 1
