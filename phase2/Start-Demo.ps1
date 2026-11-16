$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$popplerFallback = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin'
if (Test-Path -LiteralPath $popplerFallback) { $env:PATH = "$popplerFallback;$env:PATH" }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Run .\Setup.ps1 first.' }
Write-Host 'Open http://127.0.0.1:8765 ; Ctrl+C stops the server.'
& '.\.venv\Scripts\python.exe' -m uvicorn ar_companion.app:app --host 127.0.0.1 --port 8765
