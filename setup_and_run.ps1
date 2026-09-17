# ATC Tuner — one-time setup + launch
# Run from the ATC directory: .\setup_and_run.ps1

Write-Host "`n=== ATC Tuner Setup ===" -ForegroundColor Cyan

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found. Download from https://python.org" -ForegroundColor Red
    exit 1
}

# Install dependencies
Write-Host "Installing Python packages..." -ForegroundColor Yellow
python -m pip install -r requirements.txt

Write-Host "`nLaunching ATC Tuner..." -ForegroundColor Green
python atc_tuner.py
