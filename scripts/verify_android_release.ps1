Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

function Load-EnvFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path $Path)) {
        throw "출시 설정 파일을 찾을 수 없습니다. 경로: $Path. prepare_release_env_files.bat를 먼저 실행하세요."
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
        throw "$MissingMessage 경로: $Path. 로컬 Android 빌드 도구 설정은 docs\manual_test_guide.md를 확인하세요."
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
    throw "frontend 폴더를 찾을 수 없습니다. 경로: $frontend"
}

if (-not (Test-Path $android)) {
    throw "Android 프로젝트를 찾을 수 없습니다. 경로: $android"
}

if (-not (Test-Path $frontendReleaseEnv)) {
    throw "출시 설정 파일을 찾을 수 없습니다. 경로: $frontendReleaseEnv. prepare_release_env_files.bat를 먼저 실행하세요."
}

Test-RequiredPath -Path $javaHome -MissingMessage "로컬 JDK 폴더를 찾을 수 없습니다."
Test-RequiredPath -Path $androidHome -MissingMessage "로컬 Android SDK 폴더를 찾을 수 없습니다."

$oldJavaHome = $env:JAVA_HOME
$oldAndroidHome = $env:ANDROID_HOME
$oldAndroidSdkRoot = $env:ANDROID_SDK_ROOT
$oldNpmUpdateNotifier = $env:npm_config_update_notifier
$oldPath = $env:Path
$oldFrontendEnvFile = $env:ALPHAMATE_FRONTEND_ENV_FILE

try {
    $env:ALPHAMATE_FRONTEND_ENV_FILE = $frontendReleaseEnv
    Load-EnvFile -Path $frontendReleaseEnv

    $env:JAVA_HOME = $javaHome
    $env:ANDROID_HOME = $androidHome
    $env:ANDROID_SDK_ROOT = $androidHome
    $env:npm_config_update_notifier = "false"
    $env:Path = "$javaHome\bin;$androidHome\cmdline-tools\latest\bin;$androidHome\platform-tools;$oldPath"

    Push-Location $frontend
    Write-Host ""
    Write-Host "==> 서명된 Android 출시 AAB를 빌드합니다" -ForegroundColor Cyan
    & npm.cmd run mobile:release:aab
    if ($LASTEXITCODE -ne 0) {
        throw "npm run mobile:release:aab 실행에 실패했습니다. 오류 코드: $LASTEXITCODE"
    }
    Pop-Location

    if (-not (Test-Path $aabPath)) {
        throw "출시 AAB 파일이 만들어지지 않았습니다. 경로: $aabPath"
    }

    $aab = Get-Item $aabPath
    Write-Host ""
    Write-Host "Android 출시 AAB 빌드를 통과했습니다." -ForegroundColor Green
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
    $env:npm_config_update_notifier = $oldNpmUpdateNotifier
    $env:Path = $oldPath
    $env:ALPHAMATE_FRONTEND_ENV_FILE = $oldFrontendEnvFile
}
