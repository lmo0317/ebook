@echo off
title PDF to e-Book Studio
cd /d "%~dp0"
echo ========================================================
echo   Launching PDF to e-Book Studio...
echo ========================================================
"C:\Users\lmo03\AppData\Local\Programs\Python\Python312\python.exe" ebook_studio_gui.py
if errorlevel 1 (
    echo.
    echo ========================================================
    echo Error occurred! See the message above.
    echo ========================================================
    pause
)
