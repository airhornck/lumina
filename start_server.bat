@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

:: 设置 Python 路径
set PYTHONPATH=apps\api\src;packages\llm-hub\src;packages\knowledge-base\src;packages\lumina-skills\src;packages\skill-hub-client\src;packages\sop-engine\src;packages\agent-core\src;apps\intent\src;apps\orchestra\src;apps\skill-hub\src;apps\rpa\src

:: 启动服务
echo ==========================================
echo  Lumina API Server
echo ==========================================
echo.
echo 服务地址: http://localhost:8080
echo 前端页面: http://localhost:8080/debug/chat
echo API 文档: http://localhost:8080/docs
echo 健康检查: http://localhost:8080/health
echo.
echo 按 Ctrl+C 停止服务
echo ==========================================
echo.

python -m uvicorn api.main:app --host 0.0.0.0 --port 8080

pause
