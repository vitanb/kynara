<#
    commit-and-push.ps1
    Stages, commits, and pushes the Kynara repo to origin/main (Railway auto-deploys).
    Run from the repo root:  .\commit-and-push.ps1
    Optional custom message: .\commit-and-push.ps1 -Message "your message"
#>

param(
    [string]$Message = "feat: Okta agent-identity sync (provider config, sync service, role mapping, UI) + MCP gateway + tests",
    [string]$Branch  = "main",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

# --- Move to the script's own directory (repo root) ---------------------------
Set-Location -Path $PSScriptRoot
Write-Host "Repo: $(Get-Location)" -ForegroundColor Cyan

# --- 1. Repair a corrupt git index if needed ---------------------------------
git status *> $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "git index looks corrupt - repairing (rebuilds from HEAD, working files untouched)..." -ForegroundColor Yellow
    Remove-Item ".git\index.lock" -Force -ErrorAction SilentlyContinue
    Remove-Item ".git\index"      -Force -ErrorAction SilentlyContinue
    git reset | Out-Null
    git status *> $null 2>&1
    if ($LASTEXITCODE -ne 0) { throw "git is still unhealthy after repair. Resolve manually before committing." }
    Write-Host "Index repaired." -ForegroundColor Green
}

# --- 2. Keep throwaway preview images out of the repo ------------------------
$gitignore = ".gitignore"
$ignoreLines = @("docs/_ui_preview.png", "docs/_opt_*.png", "docs/_mercury_*.png", "docs/_verify_*.png")
foreach ($line in $ignoreLines) {
    if (-not (Test-Path $gitignore) -or -not (Select-String -Path $gitignore -SimpleMatch $line -Quiet)) {
        Add-Content -Path $gitignore -Value $line
    }
}
# Drop any already-tracked preview images from the index (ignore errors if absent)
git rm --cached --ignore-unmatch docs/_ui_preview.png docs/_opt_*.png docs/_mercury_*.png docs/_verify_*.png *> $null 2>&1

# --- 3. Optional: build the frontend so you don't push a broken bundle --------
if (-not $SkipBuild) {
    if (Test-Path "frontend\package.json") {
        Push-Location frontend
        # Ensure dependencies are present (tsc/vite live in node_modules\.bin).
        if (-not (Test-Path "node_modules\.bin\vite.cmd") -or -not (Test-Path "node_modules\.bin\tsc.cmd")) {
            Write-Host "Installing frontend dependencies (npm install)..." -ForegroundColor Cyan
            npm install
            if ($LASTEXITCODE -ne 0) { Pop-Location; throw "npm install failed - cannot build." }
        }
        Write-Host "Building frontend (npm run build)..." -ForegroundColor Cyan
        npm run build
        if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Frontend build failed - fix errors before pushing (or re-run with -SkipBuild)." }
        Pop-Location
        Write-Host "Build OK." -ForegroundColor Green
    }
}

# --- 4. Stage, commit, push --------------------------------------------------
git add -A

git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "Nothing staged to commit." -ForegroundColor Yellow
    exit 0
}

Write-Host "`nFiles to be committed:" -ForegroundColor Cyan
git diff --cached --name-status

git commit -m $Message
git push origin $Branch

Write-Host "`nDone. Pushed to origin/$Branch - Railway will deploy from here." -ForegroundColor Green
