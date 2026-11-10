@echo off
chcp 65001 >nul
cd /d E:\Onuri\Admin_stat

:: logs 폴더 없으면 생성
if not exist E:\Onuri\Admin_stat\logs mkdir E:\Onuri\Admin_stat\logs

:: 7일 이상 된 로그 삭제
forfiles /p E:\Onuri\Admin_stat\logs /m *.log /d -7 /c "cmd /c del @path" 2>nul

:: 오늘 날짜로 로그 파일명 생성
set LOG=E:\Onuri\Admin_stat\logs\dreamAdminStat_%date:~0,4%%date:~5,2%%date:~8,2%.log
set PYTHONIOENCODING=utf-8

:: 새 로그 파일이면 UTF-8 BOM 먼저 기록 (메모장 등에서 한글 깨짐 방지)
if not exist %LOG% powershell -NoProfile -Command "$bytes=[byte[]]@(0xEF,0xBB,0xBF);[IO.File]::WriteAllBytes('%LOG%',$bytes)"

python main.py >> %LOG% 2>&1