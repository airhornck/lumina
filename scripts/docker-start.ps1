#!/usr/bin/env pwsh
# Lumina AI营销平台 - Docker 启动脚本 (PowerShell)
# 使用方法: .\scripts\docker-start.ps1 [basic|full|browser|stop]

param(
    [Parameter()]
    [ValidateSet("basic", "full", "browser", "stop")]
    [string]$Mode = "basic"
)

Write-Host "==========================================" -ForegroundColor Blue
Write-Host "   Lumina AI营销平台 - Docker 启动脚本" -ForegroundColor Blue
Write-Host "==========================================" -ForegroundColor Blue
Write-Host ""

# 检查 Docker
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[错误] Docker 未安装" -ForegroundColor Red
    Write-Host "下载地址: https://www.docker.com/products/docker-desktop"
    exit 1
}

if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[错误] Docker Compose 未安装" -ForegroundColor Red
    exit 1
}

Write-Host "[✓] Docker 检查通过" -ForegroundColor Green

# 检查 .env 文件
if (!(Test-Path .env)) {
    Write-Host ""
    Write-Host "[警告] 未找到 .env 文件，正在从模板创建..." -ForegroundColor Yellow
    Copy-Item .env.docker .env
    Write-Host "[✓] 已创建 .env 文件" -ForegroundColor Green
    Write-Host "请编辑 .env 文件填写 API Keys，然后重新运行脚本" -ForegroundColor Yellow
    exit 0
}

$ComposeFile = "docker-compose.local.yml"

switch ($Mode) {
    "basic" {
        Write-Host "启动模式: 基础模式" -ForegroundColor Blue
        $ProfileArgs = ""
    }
    "full" {
        Write-Host "启动模式: 完整模式（含管理工具）" -ForegroundColor Blue
        $ProfileArgs = "--profile with-pgadmin --profile with-redis-insight"
    }
    "browser" {
        Write-Host "启动模式: 浏览器模式" -ForegroundColor Blue
        $ProfileArgs = "--profile with-browser"
    }
    "stop" {
        Write-Host "正在停止服务..." -ForegroundColor Yellow
        docker compose -f $ComposeFile down
        Write-Host "[✓] 服务已停止" -ForegroundColor Green
        exit 0
    }
}

Write-Host ""
Write-Host "[1/4] 正在构建镜像..." -ForegroundColor Blue
docker compose -f $ComposeFile $ProfileArgs.Split() build

Write-Host ""
Write-Host "[2/4] 启动服务..." -ForegroundColor Blue
docker compose -f $ComposeFile $ProfileArgs.Split() up -d

Write-Host ""
Write-Host "[3/4] 等待服务启动..." -ForegroundColor Blue
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "[4/4] 检查服务状态..." -ForegroundColor Blue
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | Select-String "lumina"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "   启动完成！访问地址:" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  API 服务:     http://localhost:8000" -ForegroundColor Blue
Write-Host "  Health 检查:  http://localhost:8000/health" -ForegroundColor Blue
Write-Host "  API 文档:     http://localhost:8000/docs" -ForegroundColor Blue

if ($Mode -eq "full") {
    Write-Host ""
    Write-Host "  pgAdmin:      http://localhost:5050" -ForegroundColor Blue
    Write-Host "  账号: admin@lumina.local / admin"
    Write-Host ""
    Write-Host "  Redis Insight: http://localhost:5540" -ForegroundColor Blue
}

Write-Host ""
Write-Host "常用命令:" -ForegroundColor Yellow
Write-Host "  查看日志: docker logs -f lumina-api" -ForegroundColor Blue
Write-Host "  重启服务: docker compose -f $ComposeFile restart" -ForegroundColor Blue
Write-Host "  停止服务: docker compose -f $ComposeFile down" -ForegroundColor Blue
Write-Host ""

# 测试服务
Write-Host "测试 API 连接..." -ForegroundColor Blue
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
    Write-Host "[✓] API 服务运行正常" -ForegroundColor Green
} catch {
    Write-Host "[!] API 服务启动中，请稍后检查" -ForegroundColor Yellow
}
