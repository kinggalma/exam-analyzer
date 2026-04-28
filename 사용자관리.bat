@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ========================================
echo  사용자 관리 (아이디/비밀번호 등록)
echo ========================================
python setup_users.py
pause
