# Push Master Dashboard to GitHub Pages (v2)
# v2 - 19-May-26 - SA - GITHUB SOP migration
#
# CHANGE FROM v1:
#   v1 targeted vfhqi/dashboards.git (old repo name, since renamed
#   to vfhqi/master on 07-May), with no safety guards.
#   v2 routes via COWORK\scripts\push-dashboard.sh --target master,
#   which fresh-clones from the correct vfhqi/master repo and runs
#   the three-layer D-GIT-13 defence (size-drop, line-retention,
#   fetch-and-behind, post-push secure-hash verification).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File push-to-github.ps1
#   powershell -ExecutionPolicy Bypass -File push-to-github.ps1 -Message "fix X"

param(
    [string]$Message = "manual push of master dashboard"
)

$ErrorActionPreference = "Stop"

# Locate bash.exe (Git for Windows)
$bashPaths = @(
    "C:\Program Files\Git\bin\bash.exe",
    "C:\Program Files (x86)\Git\bin\bash.exe",
    "C:\Users\richb\AppData\Local\Programs\Git\bin\bash.exe"
)
$BASH = $null
foreach ($bp in $bashPaths) {
    if (Test-Path $bp) { $BASH = $bp; break }
}
if (-not $BASH) {
    Write-Host "ERROR: bash.exe not found. Install Git for Windows or update bashPaths." -ForegroundColor Red
    exit 1
}

Write-Host "Using bash: $BASH" -ForegroundColor Gray
Write-Host "Routing through scripts/push-dashboard.sh (canonical github-push SOP)..." -ForegroundColor Cyan

# Invoke the canonical Bash SOP
& $BASH "/c/Users/richb/Documents/COWORK/scripts/push-dashboard.sh" --target master --message $Message --yes

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nDone. Live at: https://vfhqi.github.io/master/" -ForegroundColor Green
} else {
    Write-Host "`nPush exited with code $LASTEXITCODE - see Layer 1/2/3 detail above." -ForegroundColor Yellow
    exit $LASTEXITCODE
}
