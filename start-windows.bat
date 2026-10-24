@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 backend\local.py --seed
) else (
  python backend\local.py --seed
)
pause
