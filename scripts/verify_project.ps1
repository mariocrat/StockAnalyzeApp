Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Resolve-Path (Join-Path $scriptDir "..")
$python = Join-Path $root ".venv\Scripts\python.exe"
$frontend = Join-Path $root "frontend"

if (-not (Test-Path $python)) {
    throw "Python venv를 찾을 수 없습니다. 경로: $python"
}

if (-not (Test-Path $frontend)) {
    throw "frontend 폴더를 찾을 수 없습니다. 경로: $frontend"
}

function Run-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name 단계가 실패했습니다. 오류 코드: $LASTEXITCODE"
    }
}

$oldViteAppName = $env:VITE_APP_NAME
$oldNpmUpdateNotifier = $env:npm_config_update_notifier
$oldPythonUtf8 = $env:PYTHONUTF8

try {
    $env:npm_config_update_notifier = "false"
    $env:PYTHONUTF8 = "1"

    Push-Location $root
    Run-Step "백엔드 테스트" { & $python -m unittest discover -s tests }
    Run-Step "백엔드 컴파일 확인" { & $python -m compileall backend }
    Run-Step "Git 추적 파일 비밀값 검사" { & $python scripts\check_no_tracked_secrets.py }
    Pop-Location

    Push-Location $frontend
    Run-Step "프론트 출시 설정 테스트" { & npm.cmd run test:release-env }
    Run-Step "프론트 Android 브랜딩 테스트" { & npm.cmd run test:android-branding }
    Run-Step "프론트 Android Billing Library 버전 테스트" { & npm.cmd run test:android-billing }
    Run-Step "프론트 모바일 결제 테스트" { & npm.cmd run test:mobile-billing }
    Run-Step "프론트 모바일 AdMob 테스트" { & npm.cmd run test:mobile-admob }
    Run-Step "프론트 사용자 오류 로그 테스트" { & npm.cmd run test:client-events }
    Run-Step "프론트 API 오류 요청 ID 테스트" { & npm.cmd run test:api-errors }
    Run-Step "프론트 OAuth 앱 복귀 테스트" { & npm.cmd run test:oauth-app-return }
    Run-Step "프론트 앱 뒤로가기 테스트" { & npm.cmd run test:app-navigation }
    Run-Step "프론트 AI 복기 중복 요청 방지 테스트" { & npm.cmd run test:ai-idempotency }
    Run-Step "프론트 스플래시 로딩 정책 테스트" { & npm.cmd run test:splash-loading }
    Run-Step "프론트 린트" { & npm.cmd run lint }
    if (-not $env:VITE_APP_NAME) {
        $env:VITE_APP_NAME = "AlphaMate"
    }
    Run-Step "프론트 운영 빌드" { & npm.cmd run build }
    Pop-Location

    Write-Host ""
    Write-Host "프로젝트 전체 검증을 통과했습니다." -ForegroundColor Green
}
finally {
    while ((Get-Location).Path -ne $root.Path -and (Get-Location).Path.StartsWith($root.Path)) {
        Pop-Location
    }
    $env:VITE_APP_NAME = $oldViteAppName
    $env:npm_config_update_notifier = $oldNpmUpdateNotifier
    $env:PYTHONUTF8 = $oldPythonUtf8
}
