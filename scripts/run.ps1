# Run Ghostwriter on your real archive (data\). Only this computer can reach it (127.0.0.1).
#   powershell -ExecutionPolicy Bypass -File scripts\run.ps1

Set-Location (Split-Path $PSScriptRoot -Parent)
Write-Host "Open http://127.0.0.1:8000  (Ctrl+C to stop)"
& .\.venv\Scripts\python.exe -m uvicorn ghostwriter.api.main:app --host 127.0.0.1 --port 8000
