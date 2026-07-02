Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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
$javaHome = Join-Path $root ".tools\jdk\jdk-21.0.11+10"
$androidHome = Join-Path $root ".tools\android-sdk"
$apkPath = Join-Path $android "app\build\outputs\apk\debug\app-debug.apk"

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

try {
    $env:JAVA_HOME = $javaHome
    $env:ANDROID_HOME = $androidHome
    $env:ANDROID_SDK_ROOT = $androidHome
    $env:Path = "$javaHome\bin;$androidHome\cmdline-tools\latest\bin;$androidHome\platform-tools;$oldPath"

    Push-Location $frontend
    Write-Host ""
    Write-Host "==> Syncing web assets into Android" -ForegroundColor Cyan
    & npm.cmd run mobile:build
    if ($LASTEXITCODE -ne 0) {
        throw "npm run mobile:build failed with exit code $LASTEXITCODE"
    }
    Pop-Location

    Push-Location $android
    Write-Host ""
    Write-Host "==> Building Android debug APK" -ForegroundColor Cyan
    & .\gradlew.bat assembleDebug
    if ($LASTEXITCODE -ne 0) {
        throw "gradlew assembleDebug failed with exit code $LASTEXITCODE"
    }
    Pop-Location

    if (-not (Test-Path $apkPath)) {
        throw "Debug APK was not created at $apkPath"
    }

    $apk = Get-Item $apkPath
    Write-Host ""
    Write-Host "Android debug APK build passed." -ForegroundColor Green
    Write-Host "APK: $($apk.FullName)"
    Write-Host "Size: $($apk.Length) bytes"
}
finally {
    while ((Get-Location).Path -ne $root.Path -and (Get-Location).Path.StartsWith($root.Path)) {
        Pop-Location
    }
    $env:JAVA_HOME = $oldJavaHome
    $env:ANDROID_HOME = $oldAndroidHome
    $env:ANDROID_SDK_ROOT = $oldAndroidSdkRoot
    $env:Path = $oldPath
}
