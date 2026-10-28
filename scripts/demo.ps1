# Run Ghostwriter on a separate demo archive (demo-data\) filled with the fictional sample stories.
# Your real archive in data\ is never touched.
#   powershell -ExecutionPolicy Bypass -File scripts\demo.ps1
# The first run asks Gemma to analyse the 4 samples (about a minute each on a CPU).

Set-Location (Split-Path $PSScriptRoot -Parent)
$env:GW_DATA_DIR = "demo-data"
$py = ".\.venv\Scripts\python.exe"

& $py -m ghostwriter.samples
Write-Host "Open http://127.0.0.1:8000  (Ctrl+C to stop)"
& $py -m uvicorn ghostwriter.api.main:app --host 127.0.0.1 --port 8000
