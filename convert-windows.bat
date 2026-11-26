@echo off
rem Double-click this file. The program itself is in the "app" folder; this only starts it.
call "%~dp0app\convert-windows.bat" %*
exit /b %errorlevel%
