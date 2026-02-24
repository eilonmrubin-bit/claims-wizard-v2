@echo off
chcp 65001 >nul
echo ═══════════════════════════════════════
echo    אשף התביעות - סביבת פיתוח
echo ═══════════════════════════════════════
echo.

:: Start backend in new window
echo מפעיל Backend...
start "Claims Wizard - Backend" cmd /k "cd /d %~dp0backend && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: Wait a moment for backend to start
timeout /t 2 /nobreak >nul

:: Start frontend in new window
echo מפעיל Frontend...
start "Claims Wizard - Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ═══════════════════════════════════════
echo    השרתים הופעלו בחלונות נפרדים
echo.
echo    Backend:  http://localhost:8000
echo    Frontend: http://localhost:5173
echo ═══════════════════════════════════════
echo.
pause
