# 安装 Git hooks 到本地仓库
# 使用方法: .\setup-hooks.ps1

$hooksDir = "hooks"
$gitHooksDir = ".git\hooks"

if (-not (Test-Path $gitHooksDir)) {
    Write-Host "未找到 .git\hooks 目录，请确认在项目根目录运行" -ForegroundColor Red
    exit 1
}

Get-ChildItem -Path $hooksDir | ForEach-Object {
    Copy-Item $_.FullName "$gitHooksDir\$($_.Name)" -Force
    Write-Host "已安装 hook: $($_.Name)" -ForegroundColor Green
}

Write-Host ""
Write-Host "Hooks 安装完成！以后 git pull 时会自动检测依赖变更。" -ForegroundColor Cyan
