Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

function Read-AllowedEnvFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string[]]$AllowedNames
    )

    if (-not (Test-Path $Path)) {
        throw "Release environment file was not found: $Path"
    }

    $values = @{}
    Get-Content -Encoding UTF8 $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $parts = $line.Split("=", 2)
        $name = $parts[0].Trim()
        if ($AllowedNames -contains $name) {
            $values[$name] = $parts[1].Trim().Trim('"').Trim("'")
        }
    }
    return $values
}

function Test-RequiredPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$MissingMessage
    )

    if (-not (Test-Path $Path)) {
        throw "$MissingMessage Path: $Path. See docs\manual_test_guide.md."
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Resolve-Path (Join-Path $scriptDir "..")
$frontend = Join-Path $root "frontend"
$android = Join-Path $frontend "android"
$frontendReleaseEnv = Join-Path $frontend ".env.release"
$backendReleaseEnv = Join-Path $root ".env.release"
$javaHome = Join-Path $root ".tools\jdk\jdk-21.0.11+10"
$androidHome = Join-Path $root ".tools\android-sdk"
$apkPath = Join-Path $android "app\build\outputs\apk\debug\app-debug.apk"
$allowedNames = @(
    "VITE_ALPHAMATE_ENV",
    "VITE_APP_NAME",
    "VITE_ENABLE_DEV_TOOLS",
    "VITE_API_BASE",
    "VITE_KAKAO_REST_API_KEY",
    "VITE_KAKAO_REDIRECT_URI",
    "VITE_NAVER_CLIENT_ID",
    "VITE_NAVER_REDIRECT_URI",
    "VITE_GOOGLE_PLAY_PACKAGE_NAME",
    "ALPHAMATE_ANDROID_APP_NAME",
    "ALPHAMATE_ANDROID_VERSION_CODE",
    "ALPHAMATE_ANDROID_VERSION_NAME"
)
$requiredNames = @(
    "VITE_API_BASE",
    "VITE_KAKAO_REST_API_KEY",
    "VITE_KAKAO_REDIRECT_URI",
    "VITE_NAVER_CLIENT_ID",
    "VITE_NAVER_REDIRECT_URI",
    "VITE_GOOGLE_PLAY_PACKAGE_NAME"
)

Test-RequiredPath -Path $frontend -MissingMessage "Frontend folder was not found."
Test-RequiredPath -Path $android -MissingMessage "Android project was not found."
Test-RequiredPath -Path $javaHome -MissingMessage "Local JDK folder was not found."
Test-RequiredPath -Path $androidHome -MissingMessage "Local Android SDK folder was not found."

$publicValues = Read-AllowedEnvFile -Path $frontendReleaseEnv -AllowedNames $allowedNames
foreach ($name in $requiredNames) {
    if (-not $publicValues.ContainsKey($name) -or [string]::IsNullOrWhiteSpace($publicValues[$name])) {
        throw "Required public OAuth setting is missing: $name"
    }
}
if (-not $publicValues["VITE_API_BASE"].StartsWith("https://")) {
    throw "VITE_API_BASE must use HTTPS for the OAuth test APK."
}

$oldValues = @{}
foreach ($name in $allowedNames) {
    $oldValues[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}
$debugAdValues = @{
    VITE_ALPHAMATE_ENV = "development"
    VITE_ENABLE_DEV_TOOLS = "false"
    VITE_ADMOB_ANDROID_APP_ID = "ca-app-pub-3940256099942544~3347511713"
    VITE_ADMOB_REWARDED_AD_UNIT_ID = "ca-app-pub-3940256099942544/5224354917"
    VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID = "ca-app-pub-3940256099942544/1033173712"
    VITE_ADMOB_APP_OPEN_AD_UNIT_ID = "ca-app-pub-3940256099942544/9257395921"
    VITE_ADMOB_CHART_DETAIL_INTERSTITIAL_AD_UNIT_ID = "ca-app-pub-3940256099942544/1033173712"
    VITE_ADMOB_BANNER_AD_UNIT_ID = "ca-app-pub-3940256099942544/6300978111"
}
$oldDebugAdValues = @{}
foreach ($name in $debugAdValues.Keys) {
    $oldDebugAdValues[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}
$oldJavaHome = $env:JAVA_HOME
$oldAndroidHome = $env:ANDROID_HOME
$oldAndroidSdkRoot = $env:ANDROID_SDK_ROOT
$oldNpmUpdateNotifier = $env:npm_config_update_notifier
$oldPath = $env:Path

try {
    foreach ($name in $publicValues.Keys) {
        [Environment]::SetEnvironmentVariable($name, $publicValues[$name], "Process")
    }
    # Debug builds intentionally use Google's official demo ad IDs. They are never used for release AABs.
    foreach ($name in $debugAdValues.Keys) {
        [Environment]::SetEnvironmentVariable($name, $debugAdValues[$name], "Process")
    }
    $env:JAVA_HOME = $javaHome
    $env:ANDROID_HOME = $androidHome
    $env:ANDROID_SDK_ROOT = $androidHome
    $env:npm_config_update_notifier = "false"
    $env:Path = "$javaHome\bin;$androidHome\cmdline-tools\latest\bin;$androidHome\platform-tools;$oldPath"

    Push-Location $frontend
    Write-Host "==> Building web assets with production OAuth public settings" -ForegroundColor Cyan
    & npm.cmd run mobile:build
    if ($LASTEXITCODE -ne 0) {
        throw "npm run mobile:build failed with code $LASTEXITCODE"
    }
    Pop-Location

    $distFiles = Get-ChildItem (Join-Path $frontend "dist") -File -Recurse
    if (-not ($distFiles | Select-String -SimpleMatch "https://api.alphamate.co.kr" -Quiet)) {
        throw "Built web assets do not contain the production API URL."
    }
    $secretNames = @("NAVER_CLIENT_SECRET", "KAKAO_CLIENT_SECRET", "OPENAI_API_KEY", "ALPHAMATE_OPENAI_API_KEY")
    $secretValues = Read-AllowedEnvFile -Path $backendReleaseEnv -AllowedNames $secretNames
    foreach ($name in $secretValues.Keys) {
        $secretValue = $secretValues[$name]
        if ($secretValue.Length -ge 8 -and (Select-String -Path $distFiles.FullName -SimpleMatch $secretValue -Quiet)) {
            throw "A server-only secret value was found in built web assets: $name"
        }
    }

    Push-Location $android
    Write-Host "==> Building Android OAuth test APK" -ForegroundColor Cyan
    & .\gradlew.bat assembleDebug
    if ($LASTEXITCODE -ne 0) {
        throw "gradlew assembleDebug failed with code $LASTEXITCODE"
    }
    Pop-Location

    if (-not (Test-Path $apkPath)) {
        throw "OAuth test APK was not created: $apkPath"
    }

    $apk = Get-Item $apkPath
    Write-Host "Android OAuth test APK is ready." -ForegroundColor Green
    Write-Host "APK: $($apk.FullName)"
    Write-Host "Size: $($apk.Length) bytes"
}
finally {
    while ((Get-Location).Path -ne $root.Path -and (Get-Location).Path.StartsWith($root.Path)) {
        Pop-Location
    }
    foreach ($name in $allowedNames) {
        [Environment]::SetEnvironmentVariable($name, $oldValues[$name], "Process")
    }
    foreach ($name in $debugAdValues.Keys) {
        [Environment]::SetEnvironmentVariable($name, $oldDebugAdValues[$name], "Process")
    }
    $env:JAVA_HOME = $oldJavaHome
    $env:ANDROID_HOME = $oldAndroidHome
    $env:ANDROID_SDK_ROOT = $oldAndroidSdkRoot
    $env:npm_config_update_notifier = $oldNpmUpdateNotifier
    $env:Path = $oldPath
}
