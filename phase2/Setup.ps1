param([string]$Python = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $Python) {
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundledPython) { $Python = $bundledPython }
    else { $Python = (Get-Command python -ErrorAction Stop).Source }
}
& $Python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ is required.' }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
$popplerFallback = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin'
if (-not (Get-Command pdftoppm -ErrorAction SilentlyContinue)) {
    if (Test-Path -LiteralPath (Join-Path $popplerFallback 'pdftoppm.exe')) { $env:PATH = "$popplerFallback;$env:PATH" }
    else { throw 'Install Poppler and add its bin directory to PATH, then run Setup.ps1 again.' }
}
New-Item -ItemType Directory -Force -Path 'data\input' | Out-Null
$manual = Join-Path $PSScriptRoot 'data\input\BES500_USCM_IB_T23_LR.pdf'
if (-not (Test-Path -LiteralPath $manual)) { Invoke-WebRequest -Uri 'https://assets.breville.com/BES500/BES500_USCM_IB_T23_LR.pdf' -OutFile $manual }
& '.\.venv\Scripts\python.exe' -m ar_companion.cli ingest $manual --appliance-id breville-bes500
if ($LASTEXITCODE -ne 0) { throw 'Ingestion failed; inspect the error above.' }
Write-Host 'Setup complete. Run .\Start-Demo.ps1 and open http://127.0.0.1:8765'
