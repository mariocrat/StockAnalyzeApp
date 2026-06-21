Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Resolve-Path (Join-Path $scriptDir "..")
$python = Join-Path $root ".venv\Scripts\python.exe"
$frontend = Join-Path $root "frontend"

if (-not (Test-Path $python)) {
    throw "Python venv was not found at $python"
}

if (-not (Test-Path $frontend)) {
    throw "Frontend folder was not found at $frontend"
}

function Run-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Command
}

$oldViteAppName = $env:VITE_APP_NAME

try {
    Push-Location $root
    Run-Step "Backend tests" { & $python -m unittest discover -s tests }
    Run-Step "Backend compile" { & $python -m compileall backend }
    Pop-Location

    Push-Location $frontend
    Run-Step "Frontend release-env tests" { & npm.cmd run test:release-env }
    Run-Step "Frontend Android branding tests" { & npm.cmd run test:android-branding }
    Run-Step "Frontend mobile AdMob tests" { & npm.cmd run test:mobile-admob }
    Run-Step "Frontend lint" { & npm.cmd run lint }
    if (-not $env:VITE_APP_NAME) {
        $env:VITE_APP_NAME = "AlphaMate"
    }
    Run-Step "Frontend production build" { & npm.cmd run build }
    Pop-Location

    Write-Host ""
    Write-Host "All project checks passed." -ForegroundColor Green
}
finally {
    while ((Get-Location).Path -ne $root.Path -and (Get-Location).Path.StartsWith($root.Path)) {
        Pop-Location
    }
    $env:VITE_APP_NAME = $oldViteAppName
}
