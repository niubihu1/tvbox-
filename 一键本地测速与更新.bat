@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TVBox Auto Engine
python -m auto_engine.main --all
pause
