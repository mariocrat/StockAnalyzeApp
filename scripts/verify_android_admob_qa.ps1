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
        throw "$MissingMessage Path: $Path. See docs\android_admob_qa_test_guide.md."
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
$sourceApkPath = Join-Path $android "app\build\outputs\apk\debug\app-debug.apk"
$qaOutputDir = Join-Path $android "app\build\outputs\apk\qa"
$qaApkPath = Join-Path $qaOutputDir "alphamate-admob-qa.apk"
$googleDemoPublisher = "3940256099942544"
$placeholderPublisher = "0000000000000000"
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
    "VITE_ADMOB_ANDROID_APP_ID",
    "VITE_ADMOB_REWARDED_AD_UNIT_ID",
    "VITE_QA_ADVANCED_COMPARISON",
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
    "VITE_GOOGLE_PLAY_PACKAGE_NAME",
    "VITE_ADMOB_ANDROID_APP_ID",
    "VITE_ADMOB_REWARDED_AD_UNIT_ID"
)

Test-RequiredPath -Path $frontend -MissingMessage "Frontend folder was not found."
Test-RequiredPath -Path $android -MissingMessage "Android project was not found."
Test-RequiredPath -Path $javaHome -MissingMessage "Local JDK folder was not found."
Test-RequiredPath -Path $androidHome -MissingMessage "Local Android SDK folder was not found."

$publicValues = Read-AllowedEnvFile -Path $frontendReleaseEnv -AllowedNames $allowedNames
foreach ($name in $requiredNames) {
    if (-not $publicValues.ContainsKey($name) -or [string]::IsNullOrWhiteSpace($publicValues[$name])) {
        throw "Required public QA setting is missing: $name"
    }
}
if (-not $publicValues["VITE_API_BASE"].StartsWith("https://")) {
    throw "VITE_API_BASE must use HTTPS for the AdMob QA APK."
}

$admobAppId = $publicValues["VITE_ADMOB_ANDROID_APP_ID"]
$rewardedAdId = $publicValues["VITE_ADMOB_REWARDED_AD_UNIT_ID"]
if ($admobAppId -notmatch '^ca-app-pub-\d{16}~\d{10}$') {
    throw "VITE_ADMOB_ANDROID_APP_ID is not a valid Android AdMob app ID."
}
if ($rewardedAdId -notmatch '^ca-app-pub-\d{16}/\d{10}$') {
    throw "VITE_ADMOB_REWARDED_AD_UNIT_ID is not a valid rewarded ad unit ID."
}
foreach ($blockedPublisher in @($googleDemoPublisher, $placeholderPublisher)) {
    if ($admobAppId.Contains($blockedPublisher) -or $rewardedAdId.Contains($blockedPublisher)) {
        throw "The AdMob QA APK requires the real AlphaMate app and rewarded ad unit IDs."
    }
}

$qaValues = @{
    VITE_ALPHAMATE_ENV = "development"
    VITE_ENABLE_DEV_TOOLS = "false"
    VITE_QA_ADVANCED_COMPARISON = "true"
    VITE_ADMOB_ANDROID_APP_ID = $admobAppId
    VITE_ADMOB_REWARDED_AD_UNIT_ID = $rewardedAdId
    VITE_ADMOB_REVIEW_HISTORY_INTERSTITIAL_AD_UNIT_ID = "ca-app-pub-3940256099942544/1033173712"
    VITE_ADMOB_RESUME_INTERSTITIAL_AD_UNIT_ID = "ca-app-pub-3940256099942544/1033173712"
    VITE_ADMOB_CHART_DETAIL_INTERSTITIAL_AD_UNIT_ID = "ca-app-pub-3940256099942544/1033173712"
    VITE_ADMOB_BANNER_AD_UNIT_ID = "ca-app-pub-3940256099942544/6300978111"
}
$managedNames = @($allowedNames + $qaValues.Keys | Select-Object -Unique)
$oldValues = @{}
foreach ($name in $managedNames) {
    $oldValues[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
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
    # The real rewarded unit exercises SSV. Other placements stay on Google's demo units.
    # AdMob must list the phone as a test device before this QA APK is used.
    foreach ($name in $qaValues.Keys) {
        [Environment]::SetEnvironmentVariable($name, $qaValues[$name], "Process")
    }
    $env:JAVA_HOME = $javaHome
    $env:ANDROID_HOME = $androidHome
    $env:ANDROID_SDK_ROOT = $androidHome
    $env:npm_config_update_notifier = "false"
    $env:Path = "$javaHome\bin;$androidHome\cmdline-tools\latest\bin;$androidHome\platform-tools;$oldPath"

    Push-Location $frontend
    Write-Host "==> Building mobile assets for registered-device AdMob QA" -ForegroundColor Cyan
    & npm.cmd run mobile:build
    if ($LASTEXITCODE -ne 0) {
        throw "npm run mobile:build failed with code $LASTEXITCODE"
    }
    Pop-Location

    $distFiles = Get-ChildItem (Join-Path $frontend "dist") -File -Recurse
    if (-not ($distFiles | Select-String -SimpleMatch $publicValues["VITE_API_BASE"] -Quiet)) {
        throw "Built web assets do not contain the configured production API URL."
    }
    if (-not ($distFiles | Select-String -SimpleMatch $rewardedAdId -Quiet)) {
        throw "Built web assets do not contain the configured AlphaMate rewarded ad unit ID."
    }
    if (-not ($distFiles | Select-String -SimpleMatch "luna-terra-v1" -Quiet)) {
        throw "Built web assets do not contain the QA advanced comparison feature."
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
    Write-Host "==> Building registered-device AdMob QA APK" -ForegroundColor Cyan
    & .\gradlew.bat clean assembleDebug --rerun-tasks
    if ($LASTEXITCODE -ne 0) {
        throw "gradlew clean assembleDebug failed with code $LASTEXITCODE"
    }
    Pop-Location

    if (-not (Test-Path $sourceApkPath)) {
        throw "AdMob QA APK was not created: $sourceApkPath"
    }
    New-Item -ItemType Directory -Path $qaOutputDir -Force | Out-Null
    Copy-Item -LiteralPath $sourceApkPath -Destination $qaApkPath -Force
    if (-not (Test-Path $qaApkPath)) {
        throw "AdMob QA APK copy was not created: $qaApkPath"
    }

    $apk = Get-Item $qaApkPath
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $qaApkPath).Hash
    Write-Host "Android AdMob QA APK is ready." -ForegroundColor Green
    Write-Host "APK: $($apk.FullName)"
    Write-Host "Size: $($apk.Length) bytes"
    Write-Host "SHA256: $hash"
    Write-Host "Use only on a device registered as an AdMob test device." -ForegroundColor Yellow
}
finally {
    while ((Get-Location).Path -ne $root.Path -and (Get-Location).Path.StartsWith($root.Path)) {
        Pop-Location
    }
    foreach ($name in $managedNames) {
        [Environment]::SetEnvironmentVariable($name, $oldValues[$name], "Process")
    }
    $env:JAVA_HOME = $oldJavaHome
    $env:ANDROID_HOME = $oldAndroidHome
    $env:ANDROID_SDK_ROOT = $oldAndroidSdkRoot
    $env:npm_config_update_notifier = $oldNpmUpdateNotifier
    $env:Path = $oldPath
}
