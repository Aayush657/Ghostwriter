"""Self-check tests. They need no models and no running Ollama."""

from ghostwriter import selfcheck
from ghostwriter.config import settings


def test_has_model_accepts_implicit_latest_tag():
    assert selfcheck.has_model(["gemma4:latest"], "gemma4")
    assert selfcheck.has_model(["gemma4:e4b"], "gemma4:e4b")
    assert not selfcheck.has_model(["gemma4:e2b"], "gemma4:e4b")


def test_fts5_with_trigram_is_available():
    assert selfcheck.check_fts5().ok


def test_ollama_down_reports_a_plain_fix(monkeypatch):
    monkeypatch.setattr(settings, "ollama_url", "http://127.0.0.1:9")  # nothing listens on port 9
    [check] = selfcheck.check_ollama()
    assert not check.ok
    assert "ollama serve" in check.fix


def test_missing_whisper_weights_are_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "models_dir", tmp_path)
    check = selfcheck.check_whisper()
    assert not check.ok
    assert "setup.ps1" in check.fix
