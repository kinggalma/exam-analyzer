@echo off
chcp 65001 > nul
cd /d "%~dp0"

if not exist config.yaml (
    echo [경고] config.yaml 파일이 없습니다.
    echo 사용자관리.bat 을 먼저 실행하여 사용자를 등록하세요.
    pause
    exit /b
)

echo 건설안전기술사 기출문제 분석 프로그램 시작...
echo 브라우저가 자동으로 열립니다. (http://localhost:8501)
python -m streamlit run app.py --server.headless false
pause
