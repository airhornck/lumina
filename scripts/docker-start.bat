@echo off
chcp 65001 >nul
title Lumina Docker 启动脚本

echo ==========================================
echo    Lumina AI营销平台 - Docker 启动脚本
echo ==========================================
echo.

REM 检查 Docker 是否安装
docker --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker 未安装，请先安装 Docker Desktop
    echo 下载地址: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM 检查 Docker Compose
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker Compose 未安装
    pause
    exit /b 1
)

echo [✓] Docker 检查通过

REM 检查 .env 文件
if not exist .env (
    echo.
    echo [警告] 未找到 .env 文件，正在从模板创建...
    copy .env.docker .env
    echo [✓] 已创建 .env 文件，请编辑填写 API Keys
    echo.
    notepad .env
    echo 保存 .env 后按任意键继续...
    pause >nul
)

echo.
echo 选择启动模式:
echo   [1] 基础模式 (API + PostgreSQL + Redis)
echo   [2] 完整模式 (+ pgAdmin + Redis Insight)
echo   [3] 带浏览器模式 (+ Playwright)
echo   [4] 停止所有服务

set /p mode="请输入选项 (1-4): "

if "%mode%"=="1" goto basic
if "%mode%"=="2" goto full
if "%mode%"=="3" goto browser
if "%mode%"=="4" goto stop
goto invalid

:basic
echo.
echo [1/4] 正在构建镜像...
docker compose -f docker-compose.local.yml build

echo.
echo [2/4] 启动服务...
docker compose -f docker-compose.local.yml up -d

goto check

:full
echo.
echo [1/4] 正在构建镜像...
docker compose -f docker-compose.local.yml --profile with-pgadmin --profile with-redis-insight build

echo.
echo [2/4] 启动服务（含管理工具）...
docker compose -f docker-compose.local.yml --profile with-pgadmin --profile with-redis-insight up -d

goto check

:browser
echo.
echo [1/4] 正在构建镜像...
docker compose -f docker-compose.local.yml --profile with-browser build

echo.
echo [2/4] 启动服务（含浏览器）...
docker compose -f docker-compose.local.yml --profile with-browser up -d

goto check

:stop
echo.
echo 正在停止服务...
docker compose -f docker-compose.local.yml down
echo [✓] 服务已停止
pause
exit /b 0

:check
echo.
echo [3/4] 等待服务启动...
timeout /t 5 /nobreak >nul

echo.
echo [4/4] 检查服务状态...
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo ==========================================
echo    启动完成！访问地址:
echo ==========================================
echo.
echo   API 服务:     http://localhost:8000
echo   Health 检查:  http://localhost:8000/health
echo   API 文档:     http://localhost:8000/docs
echo.
if "%mode%"=="2" (
    echo   pgAdmin:      http://localhost:5050
echo   账号: admin@lumina.local / admin
    echo.
    echo   Redis Insight: http://localhost:5540
    echo.
)
echo 常用命令:
echo   查看日志: docker logs -f lumina-api
echo   重启服务: docker compose -f docker-compose.local.yml restart
echo   停止服务: docker compose -f docker-compose.local.yml down
echo.
pause
exit /b 0

:invalid
echo [错误] 无效的选项
pause
exit /b 1
