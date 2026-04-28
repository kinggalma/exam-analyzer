@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ========================================
echo  GitHub Gist 초기 설정 (최초 1회만 실행)
echo  이후 사용자관리.bat 변경 자동 반영됨
echo ========================================
python init_gist.py
pause
