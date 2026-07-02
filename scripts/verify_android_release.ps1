Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Load-EnvFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path $Path)) {
        throw "Release env file was not found at $Path. Run prepare_release_env_files.bat first."
    }

    Get-Content -Encoding UTF8 $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $parts = $line.Split("=", 2)
        $name = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if ($name) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Test-RequiredPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$MissingMessage
    )

    if (-not (Test-Path $Path)) {
        throw "$MissingMessage at $Path. See docs\manual_test_guide.md for the local Android build tool setup."
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Resolve-Path (Join-Path $scriptDir "..")
$frontend = Join-Path $root "frontend"
$android = Join-Path $frontend "android"
$frontendReleaseEnv = Join-Path $frontend ".env.release"
$javaHome = Join-Path $root ".tools\jdk\jdk-21.0.11+10"
$androidHome = Join-Path $root ".tools\android-sdk"
$aabPath = Join-Path $android "app\build\outputs\bundle\release\app-release.aab"

if (-not (Test-Path $frontend)) {
    throw "Frontend folder was not found at $frontend"
}

if (-not (Test-Path $android)) {
    throw "Android project was not found at $android"
}

Test-RequiredPath -Path $javaHome -MissingMessage "Local JDK folder was not found"
Test-RequiredPath -Path $androidHome -MissingMessage "Local Android SDK folder was not found"

$oldJavaHome = $env:JAVA_HOME
$oldAndroidHome = $env:ANDROID_HOME
$oldAndroidSdkRoot = $env:ANDROID_SDK_ROOT
$oldPath = $env:Path
$oldFrontendEnvFile = $env:ALPHAMATE_FRONTEND_ENV_FILE

try {
    $env:ALPHAMATE_FRONTEND_ENV_FILE = $frontendReleaseEnv
    Load-EnvFile -Path $frontendReleaseEnv

    $env:JAVA_HOME = $javaHome
    $env:ANDROID_HOME = $androidHome
    $env:ANDROID_SDK_ROOT = $androidHome
    $env:Path = "$javaHome\bin;$androidHome\cmdline-tools\latest\bin;$androidHome\platform-tools;$oldPath"

    Push-Location $frontend
    Write-Host ""
    Write-Host "==> Building signed Android release AAB" -ForegroundColor Cyan
    & npm.cmd run mobile:release:aab
    if ($LASTEXITCODE -ne 0) {
        throw "npm run mobile:release:aab failed with exit code $LASTEXITCODE"
    }
    Pop-Location

    if (-not (Test-Path $aabPath)) {
        throw "Release AAB was not created at $aabPath"
    }

    $aab = Get-Item $aabPath
    Write-Host ""
    Write-Host "Android release AAB build passed." -ForegroundColor Green
    Write-Host "AAB: $($aab.FullName)"
    Write-Host "Size: $($aab.Length) bytes"
}
finally {
    while ((Get-Location).Path -ne $root.Path -and (Get-Location).Path.StartsWith($root.Path)) {
        Pop-Location
    }
    $env:JAVA_HOME = $oldJavaHome
    $env:ANDROID_HOME = $oldAndroidHome
    $env:ANDROID_SDK_ROOT = $oldAndroidSdkRoot
    $env:Path = $oldPath
    $env:ALPHAMATE_FRONTEND_ENV_FILE = $oldFrontendEnvFile
}
