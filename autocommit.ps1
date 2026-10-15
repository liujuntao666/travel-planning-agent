param(
    [string]$Message = ""
)

# 未传提交说明时，用时间戳兜底
if ([string]::IsNullOrWhiteSpace($Message)) {
    $Message = "auto: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
}

git rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 当前目录不是 git 仓库。" -ForegroundColor Red
    exit 1
}

git add -A

$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Host "[跳过] 没有需要提交的变更。" -ForegroundColor Yellow
    exit 0
}

Write-Host "[暂存] 即将提交：" -ForegroundColor Cyan
$staged | ForEach-Object { Write-Host "   $_" }

git commit -m $Message
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 提交失败。" -ForegroundColor Red
    exit 1
}

git push
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 推送失败，请检查网络或登录凭据。" -ForegroundColor Red
    exit 1
}

Write-Host "[完成] 已提交并推送到 GitHub。" -ForegroundColor Green
