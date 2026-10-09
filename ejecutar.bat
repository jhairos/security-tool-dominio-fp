@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Security Tool Jairo Suntaxi C
py -3 main.py
if errorlevel 1 pause
