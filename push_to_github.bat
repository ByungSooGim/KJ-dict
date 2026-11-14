@echo off
cd /d "%~dp0"
echo ========================================================
echo   [경주말 방언사전] GitHub 자동 동기화 및 푸시
echo ========================================================
echo.

echo 1. 변경된 파일 스테이징 중...
git add index.html demo_prosody.html "경주방언사전_사용설명서.html" "경주방언사전_사용설명서.md" images/ json_parsing20260927.py generate_dialect_prosody.py edge_server.py json_parsing.py gyeongju_dict.json .gitignore push_to_github.bat push_to_github.ps1

echo 2. 커밋 생성 중...
git commit -m "경주방언사전 업데이트"

echo 3. GitHub (origin/main) 푸시 중...
git push origin main

if errorlevel 1 (
    echo.
    echo [안내] 최초 1회 실행 시 웹브라우저에 GitHub 로그인 창이 뜹니다.
    echo 브라우저에서 'Authorize GitCredentialManager'를 승인해 주세요.
) else (
    echo.
    echo ========================================================
    echo  [성공] GitHub에 정상적으로 푸시되었습니다!
    echo  저장소: https://github.com/ByungSooGim/KJ-dict
    echo  웹사전: https://byungsoogim.github.io/KJ-dict/
    echo  설명서: https://byungsoogim.github.io/KJ-dict/경주방언사전_사용설명서.html
    echo ========================================================
)

echo.
pause
