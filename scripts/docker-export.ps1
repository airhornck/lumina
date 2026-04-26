# Lumina Docker 镜像构建与导出脚本
# 使用方法: .\scripts\docker-export.ps1 [镜像标签] [输出路径]
# 示例: .\scripts\docker-export.ps1 lumina:latest .\lumina-image.tar

param(
    [string]$ImageTag = "lumina:latest",
    [string]$OutputPath = "lumina-image.tar"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Blue
Write-Host "   Lumina Docker 镜像构建与导出" -ForegroundColor Blue
Write-Host "==========================================" -ForegroundColor Blue
Write-Host ""

# 检查 Docker
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[错误] 未找到 Docker，请先安装 Docker Desktop" -ForegroundColor Red
    Write-Host "下载地址: https://www.docker.com/products/docker-desktop"
    exit 1
}

Write-Host "[1/3] 正在构建镜像 $ImageTag ..." -ForegroundColor Blue

$buildArgs = @(
    "build",
    "-t", $ImageTag,
    "-f", "Dockerfile",
    "."
)

docker @buildArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 镜像构建失败" -ForegroundColor Red
    exit 1
}

Write-Host "[✓] 镜像构建完成" -ForegroundColor Green
Write-Host ""

Write-Host "[2/3] 正在导出镜像到 $OutputPath ..." -ForegroundColor Blue

docker save $ImageTag -o $OutputPath
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 镜像导出失败" -ForegroundColor Red
    exit 1
}

Write-Host "[✓] 镜像导出完成" -ForegroundColor Green
Write-Host ""

# 显示文件大小
$item = Get-Item $OutputPath -ErrorAction SilentlyContinue
if ($item) {
    $sizeMB = [math]::Round($item.Length / 1MB, 2)
    Write-Host "输出文件: $($item.FullName)" -ForegroundColor Blue
    Write-Host "文件大小: ${sizeMB} MB" -ForegroundColor Blue
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "   完成！后续使用命令:" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  加载镜像:" -ForegroundColor Yellow
Write-Host "    docker load -i $OutputPath" -ForegroundColor Blue
Write-Host ""
Write-Host "  运行容器:" -ForegroundColor Yellow
Write-Host "    docker run -d -p 8000:8000 --env-file .env $ImageTag" -ForegroundColor Blue
Write-Host ""
Write-Host '  如需压缩传输，可执行:' -ForegroundColor Yellow
Write-Host '    Compress-Archive -Path $OutputPath -DestinationPath $OutputPath.zip' -ForegroundColor Blue
Write-Host ""
