$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "py"
}

& $python export_public.py
& $python export_static_public.py

New-Item -ItemType Directory -Force -Path ".\docs" | Out-Null
Copy-Item ".\public\public_log.csv" ".\docs\public_log.csv" -Force
Copy-Item ".\public\public_summary.json" ".\docs\public_summary.json" -Force
Copy-Item ".\public\index.html" ".\docs\index.html" -Force

git add public/public_log.csv public/public_summary.json public/index.html docs/public_log.csv docs/public_summary.json docs/index.html

git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "No public dashboard changes to publish."
    exit 0
}

git commit -m "Update public BarPass log"
git push
