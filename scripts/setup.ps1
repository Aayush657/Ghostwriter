# One-command setup for Windows. From the project folder run:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
# Needs the internet once (Python packages + Whisper weights). After that Ghostwriter runs offline.
# ffmpeg and Ollama are installed separately: see README > Setup.

Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) { py -3.11 -m venv .venv }
$py = ".\.venv\Scripts\python.exe"

& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt
if ($LASTEXITCODE) { Write-Error "pip install failed"; exit 1 }

# Hugging Face's Xet transfer stalled on the dev machine; plain HTTPS downloads are reliable.
$env:HF_HUB_DISABLE_XET = "1"
$env:HF_HUB_DISABLE_TELEMETRY = "1"
& $py -c @"
from faster_whisper import download_model
from ghostwriter.config import settings
p = settings.whisper_path
if not (p / 'model.bin').exists():
    download_model(settings.whisper_model, output_dir=str(p))
print('Whisper weights:', p)
"@
if ($LASTEXITCODE) { Write-Error "Whisper download failed"; exit 1 }

# The ghost voice model for Piper (optional feature; the app works without it). CC BY-SA 4.0.
$voiceDir = "models\piper"
$voice = "en_GB-northern_english_male-medium"
$voiceUrl = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/northern_english_male/medium"
New-Item -ItemType Directory -Force $voiceDir | Out-Null
foreach ($file in "$voice.onnx", "$voice.onnx.json", "MODEL_CARD") {
    if (-not (Test-Path "$voiceDir\$file")) {
        curl.exe -sSfL --retry 8 --retry-all-errors -o "$voiceDir\$file" "$voiceUrl/$file"
    }
}

& $py -m ghostwriter.selfcheck
