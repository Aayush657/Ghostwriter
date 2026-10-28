"""Environment self-check: which local pieces are available right now.

Run:  python -m ghostwriter.selfcheck          fast, loads no models
      python -m ghostwriter.selfcheck --ping   also asks Gemma for one line and reports tokens/sec

The web app runs the same checks at startup. Nothing here touches the internet:
Ollama is on localhost and the Whisper weights load from disk.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass

import httpx

from ghostwriter.config import settings


@dataclass
class Check:
    """Result of one check. `fix` is a plain-language next step when it fails."""

    name: str
    ok: bool
    detail: str
    fix: str = ""
    required: bool = True


def check_python() -> Check:
    ok = sys.version_info >= (3, 11)
    return Check("Python", ok, sys.version.split()[0], "Install Python 3.11+ from python.org.")


def check_fts5() -> Check:
    """Seance search needs SQLite's FTS5 index with the script-agnostic trigram tokenizer."""
    con = sqlite3.connect(":memory:")
    try:
        con.execute("CREATE VIRTUAL TABLE t USING fts5(body, tokenize='trigram')")
        return Check("SQLite FTS5", True, f"SQLite {sqlite3.sqlite_version}, trigram tokenizer available")
    except sqlite3.OperationalError as exc:
        return Check("SQLite FTS5", False, str(exc), "Use the python.org build of Python 3.11+.")
    finally:
        con.close()


def check_ffmpeg() -> Check:
    path = shutil.which(settings.ffmpeg_bin)
    if not path:
        return Check("ffmpeg", False, f"'{settings.ffmpeg_bin}' not found",
                     "winget install --id Gyan.FFmpeg -e, then open a new terminal "
                     "(or set GW_FFMPEG_BIN to the full path of ffmpeg.exe).")
    out = subprocess.run([path, "-version"], capture_output=True, text=True, check=False).stdout
    return Check("ffmpeg", True, out.splitlines()[0] if out else path)


def has_model(installed: list[str], wanted: str) -> bool:
    """Ollama lists a model pulled as 'gemma4' under the name 'gemma4:latest'."""
    return wanted in installed or f"{wanted}:latest" in installed


def check_ollama() -> list[Check]:
    """Is the Ollama server up, and has the configured Gemma model been pulled?"""
    url = settings.ollama_url
    try:
        version = httpx.get(f"{url}/api/version", timeout=3).json()["version"]
        installed = [m["name"] for m in httpx.get(f"{url}/api/tags", timeout=3).json()["models"]]
    except httpx.HTTPError as exc:
        return [Check("Ollama", False, f"not reachable at {url} ({type(exc).__name__})",
                      "Start Ollama from the Start menu, or run: ollama serve")]
    server = Check("Ollama", True, f"version {version} at {url}")
    if has_model(installed, settings.llm_model):
        return [server, Check("Gemma model", True, settings.llm_model)]
    have = ", ".join(installed) or "none"
    return [server, Check("Gemma model", False, f"{settings.llm_model} not pulled (have: {have})",
                          f"ollama pull {settings.llm_model}")]


def check_whisper() -> Check:
    """faster-whisper installed, and its weights already on disk (so it never downloads at runtime)."""
    if importlib.util.find_spec("faster_whisper") is None:
        return Check("Whisper", False, "faster-whisper not installed", "pip install -r requirements.txt")
    path = settings.whisper_path
    if not (path / "model.bin").exists():
        return Check("Whisper", False, f"model '{settings.whisper_model}' not found in {path}",
                     "Run scripts\\setup.ps1 once while online.")
    return Check("Whisper", True,
                 f"faster-whisper {settings.whisper_model} ({settings.whisper_compute_type}) at {path}")


def check_tts() -> Check:
    """The ghost voice is optional: the app works without it."""
    if not settings.tts_enabled:
        return Check("Piper TTS", False, "turned off (GW_TTS_ENABLED=false)", required=False)
    path = shutil.which("piper")
    if not path:
        return Check("Piper TTS", False, "not installed", "Optional. See README > Ghost voice.",
                     required=False)
    return Check("Piper TTS", True, path, required=False)


def ping_gemma() -> Check:
    """Ask Gemma for one short line and report generation speed from Ollama's own timings."""
    body = {
        "model": settings.llm_model,
        "stream": False,
        "think": False,
        "options": {"num_ctx": settings.llm_num_ctx},  # same as the app, so Ollama doesn't reload the model
        "messages": [{"role": "user",
                      "content": "In one short, eerie sentence, announce that the archive is awake."}],
    }
    try:
        resp = httpx.post(f"{settings.ollama_url}/api/chat", json=body, timeout=600)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        return Check("Gemma reply", False, str(exc), "Check `ollama list` and GW_LLM_MODEL in .env.")
    data = resp.json()
    tokens_per_s = data["eval_count"] / (data["eval_duration"] / 1e9)
    load_s = data.get("load_duration", 0) / 1e9
    reply = data["message"]["content"].strip()
    return Check("Gemma reply", True, f'"{reply}" ({tokens_per_s:.1f} tokens/s, model load {load_s:.1f}s)')


def run_checks(ping: bool = False) -> list[Check]:
    checks = [check_python(), check_fts5(), check_ffmpeg(), *check_ollama(), check_whisper(), check_tts()]
    gemma_ready = any(c.name == "Gemma model" and c.ok for c in checks)
    if ping and gemma_ready:
        checks.append(ping_gemma())
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Ghostwriter's local services.")
    parser.add_argument("--ping", action="store_true", help="also ask Gemma for a reply (slow on first load)")
    checks = run_checks(ping=parser.parse_args().ping)
    for c in checks:
        mark = "ok" if c.ok else ("FAIL" if c.required else "--")
        print(f"[{mark:^4}] {c.name:<12} {c.detail}")
        if not c.ok and c.fix:
            print(f"{'':19}fix: {c.fix}")
    failed = [c for c in checks if c.required and not c.ok]
    print("\nAll required services are ready." if not failed else f"\n{len(failed)} required check(s) failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
