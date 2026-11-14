# GitHub 웹사전 및 설명서 자동 동기화 및 푸시 스크립트 (KJ-dict)
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  [경주말 방언사전] GitHub 웹페이지 자동 동기화 및 푸시" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

Write-Host "1. 원격 저장소 최신 상태 확인 중..." -ForegroundColor Yellow
git fetch origin main

Write-Host "2. 변경 파일 및 신규 파일(설명서, 이미지 등) 스테이징 중..." -ForegroundColor Yellow
git add index.html demo_prosody.html "경주방언사전_사용설명서.html" "경주방언사전_사용설명서.md" images/ json_parsing20260927.py generate_dialect_prosody.py edge_server.py json_parsing.py gyeongju_dict.json .gitignore push_to_github.bat push_to_github.ps1

Write-Host "3. 커밋 생성..." -ForegroundColor Yellow
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
git commit -m "경주방언사전 업데이트 ($timestamp)"

Write-Host "4. GitHub (origin/main) 푸시 중..." -ForegroundColor Yellow
git push origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[성공] https://github.com/ByungSooGim/KJ-dict 에 푸시 완료!" -ForegroundColor Green
    Write-Host "웹사전 바로가기: https://byungsoogim.github.io/KJ-dict/" -ForegroundColor Green
    Write-Host "설명서 바로가기: https://byungsoogim.github.io/KJ-dict/경주방언사전_사용설명서.html`n" -ForegroundColor Green
} else {
    Write-Host "`n[알림] 푸시 결과를 확인하세요 (오류코드: $LASTEXITCODE)`n" -ForegroundColor Red
}
