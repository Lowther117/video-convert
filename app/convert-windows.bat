@echo off
setlocal
title Video converter (Mac + PC compatible MP4)
cd /d "%~dp0"

REM --- find Python, install it if missing -------------------------------------
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY ( python -c "import sys" >nul 2>&1 && set "PY=python" )
if not defined PY (
    echo Python not found - installing with winget...
    winget install --id Python.Python.3.13 -e --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo winget could not install Python. Install it from python.org and re-run.
        pause & exit /b 1
    )
    echo Python installed. Close this window, open a NEW one and run this .bat again.
    pause & exit /b 0
)

REM --- folder: dragged onto the .bat, or typed in ------------------------------
if "%~1"=="" (
    set /p "FOLDER=Folder of videos to convert: "
) else (
    set "FOLDER=%~1"
)
set "FOLDER=%FOLDER:"=%"

%PY% "%~dp0convert_videos.py" "%FOLDER%" %2 %3 %4
echo.
pause
