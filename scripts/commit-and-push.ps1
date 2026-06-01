# commit-and-push.ps1
Set-Location "$PSScriptRoot\.."

Write-Host "=== Clearing git locks ===" -ForegroundColor Cyan
@(".git\index.lock", ".git\HEAD.lock") | ForEach-Object {
    if (Test-Path $_) { Remove-Item $_ -Force; Write-Host "Removed: $_" }
}

Write-Host "=== Staging all changes ===" -ForegroundColor Cyan
git add -A

Write-Host "=== Status ===" -ForegroundColor Cyan
git status --short

Write-Host "=== Committing ===" -ForegroundColor Cyan
git commit -m "feat: all 9 improvements - analytics, email/PD alerts, templates, wizard, webhook test, changelog, API explorer, nav groups, DB migration"

if ($LASTEXITCODE -eq 0) {
    Write-Host "=== Pushing ===" -ForegroundColor Cyan
    git push origin main
    if ($LASTEXITCODE -eq 0) {
        Write-Host "DONE. Trigger deploy:" -ForegroundColor Green
        Write-Host "  https://github.com/vitanb/kynara/actions" -ForegroundColor Yellow
        Write-Host "  Deploy -> Run workflow -> production -> Run workflow" -ForegroundColor Yellow
    }
} else {
    Write-Host "Nothing new to commit." -ForegroundColor Yellow
    git log --oneline -3
}
