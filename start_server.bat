@echo off
chcp 65001 >nul
title Firefly Server
echo Setting API key...
REM 请先设置环境变量 DEEPSEEK_APIKEY 后再运行（不要把真实密钥写进本文件）
if "%DEEPSEEK_APIKEY%"=="" echo [WARN] DEEPSEEK_APIKEY 未设置
echo Starting server...
python main.py
pause