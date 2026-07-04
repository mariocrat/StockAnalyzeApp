Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

function Test-RequiredPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$MissingMessage
    )

    if (-not (Test-Path $Path)) {
        throw "$MissingMessage 경로: $Path. 로컬 Android 빌드 도구 설정은 docs\manual_test_guide.md를 확인하세요."
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
    throw "frontend 폴더를 찾을 수 없습니다. 경로: $frontend"
}

if (-not (Test-Path $android)) {
    throw "Android 프로젝트를 찾을 수 없습니다. 경로: $android"
}

Test-RequiredPath -Path $javaHome -MissingMessage "로컬 JDK 폴더를 찾을 수 없습니다."
Test-RequiredPath -Path $androidHome -MissingMessage "로컬 Android SDK 폴더를 찾을 수 없습니다."

$oldJavaHome = $env:JAVA_HOME
$oldAndroidHome = $env:ANDROID_HOME
$oldAndroidSdkRoot = $env:ANDROID_SDK_ROOT
$oldNpmUpdateNotifier = $env:npm_config_update_notifier
$oldPath = $env:Path

try {
    $env:JAVA_HOME = $javaHome
    $env:ANDROID_HOME = $androidHome
    $env:ANDROID_SDK_ROOT = $androidHome
    $env:npm_config_update_notifier = "false"
    $env:Path = "$javaHome\bin;$androidHome\cmdline-tools\latest\bin;$androidHome\platform-tools;$oldPath"

    Push-Location $frontend
    Write-Host ""
    Write-Host "==> 웹 앱 파일을 Android 프로젝트에 동기화합니다" -ForegroundColor Cyan
    & npm.cmd run mobile:build
    if ($LASTEXITCODE -ne 0) {
        throw "npm run mobile:build 실행에 실패했습니다. 오류 코드: $LASTEXITCODE"
    }
    Pop-Location

    Push-Location $android
    Write-Host ""
    Write-Host "==> Android 디버그 APK를 빌드합니다" -ForegroundColor Cyan
    & .\gradlew.bat assembleDebug
    if ($LASTEXITCODE -ne 0) {
        throw "gradlew assembleDebug 실행에 실패했습니다. 오류 코드: $LASTEXITCODE"
    }
    Pop-Location

    if (-not (Test-Path $apkPath)) {
        throw "디버그 APK 파일이 만들어지지 않았습니다. 경로: $apkPath"
    }

    $apk = Get-Item $apkPath
    Write-Host ""
    Write-Host "Android 디버그 APK 빌드를 통과했습니다." -ForegroundColor Green
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
    $env:npm_config_update_notifier = $oldNpmUpdateNotifier
    $env:Path = $oldPath
}
