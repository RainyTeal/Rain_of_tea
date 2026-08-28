@echo off
chcp 65001 >nul
echo 正在安装依赖（使用清华镜像）...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
echo 安装完成
pause
